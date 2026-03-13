from __future__ import annotations
import logging
import re
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from .base import BaseChannel
from ..bus.queue import MessageBus
from ..bus.events import InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096


def _markdown_to_html(text: str) -> str:
    if not text:
        return ""

    code_blocks: list[str] = []
    def _save_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"
    text = re.sub(r'```[\w]*\n?([\s\S]*?)```', _save_block, text)

    inline_codes: list[str] = []
    def _save_inline(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"
    text = re.sub(r'`([^`]+)`', _save_inline, text)

    text = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^>\s*(.*)$', r'\1', text, flags=re.MULTILINE)

    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    text = re.sub(r'(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])', r'<i>\1</i>', text)
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)
    text = re.sub(r'^[-*]\s+', '• ', text, flags=re.MULTILINE)

    def _esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    for i, code in enumerate(inline_codes):
        text = text.replace(f"\x00IC{i}\x00", f"<code>{_esc(code)}</code>")
    for i, code in enumerate(code_blocks):
        text = text.replace(f"\x00CB{i}\x00", f"<pre><code>{_esc(code)}</code></pre>")

    return text


class TelegramChannel(BaseChannel):
    name = "telegram"

    def __init__(self, bus: MessageBus, token: str, allowed_users: list[str], media_dir: Path | None = None):
        super().__init__(config=None, bus=bus)
        self._token = token
        self._allowed_users = set(allowed_users) if allowed_users else set()
        self._media_dir = media_dir
        self._app: Application | None = None

    def _is_allowed(self, username: str) -> bool:
        if not self._allowed_users:
            return True
        return username in self._allowed_users

    async def _download_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
        if not self._media_dir or not update.message or not update.message.photo:
            return None
        photo = update.message.photo[-1]
        try:
            f = await context.bot.get_file(photo.file_id)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self._media_dir / f"{ts}_{photo.file_unique_id}.jpg"
            self._media_dir.mkdir(parents=True, exist_ok=True)
            await f.download_to_drive(path)
            logger.debug("Downloaded photo to %s", path)
            return str(path)
        except Exception:
            logger.exception("Failed to download photo")
            return None

    async def _handle_tg_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not user or not self._is_allowed(user.username or ""):
            logger.debug("Ignored message from %s", user)
            return
        if not update.message:
            return

        photo_path = await self._download_photo(update, context)
        text = update.message.text or update.message.caption or ""
        media: list[str] = []

        if photo_path:
            media.append(photo_path)
            text = f"[Image: {photo_path}]\n\n{text}" if text else f"[Image: {photo_path}]"
        elif not text:
            return

        reply = update.message.reply_to_message
        if reply and reply.text:
            sender_name = reply.from_user.first_name if reply.from_user else "Unknown"
            text = f"[Replying to {sender_name}: {reply.text}]\n\n{text}"

        chat_id = str(update.effective_chat.id)
        thread_id = str(update.message.message_thread_id) if update.message.message_thread_id else ""
        sender = user.username or ""
        logger.debug("Telegram inbound: chat=%s thread=%s user=%s text=%s", chat_id, thread_id, sender, text[:100])

        msg = InboundMessage(channel=self.name, sender_id=sender, chat_id=chat_id, content=text, thread_id=thread_id, media=media)
        await self.bus.publish_inbound(msg)

    async def send_typing(self, chat_id: str, thread_id: str = "") -> None:
        if not self._app:
            return
        try:
            kwargs: dict = {"chat_id": int(chat_id), "action": "typing"}
            if thread_id:
                kwargs["message_thread_id"] = int(thread_id)
            await self._app.bot.send_chat_action(**kwargs)
        except Exception:
            logger.debug("Failed to send typing to %s", chat_id)

    async def send(self, msg: OutboundMessage) -> None:
        if not self._app:
            return
        thread_kwargs: dict = {}
        if msg.thread_id:
            thread_kwargs["message_thread_id"] = int(msg.thread_id)
        html = _markdown_to_html(msg.content)
        chunks = self._split_message(html)
        for chunk in chunks:
            try:
                await self._app.bot.send_message(
                    chat_id=int(msg.chat_id), text=chunk, parse_mode="HTML",
                    **thread_kwargs,
                )
            except Exception:
                logger.debug("HTML send failed, falling back to plain text")
                plain_chunks = self._split_message(msg.content)
                for pc in plain_chunks:
                    await self._app.bot.send_message(
                        chat_id=int(msg.chat_id), text=pc, **thread_kwargs,
                    )
                return

    async def start(self) -> None:
        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, self._handle_tg_message))
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(
            allowed_updates=["message"],
            drop_pending_updates=True,
        )
        logger.info("Telegram channel started")

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    @staticmethod
    def _split_message(text: str) -> list[str]:
        if len(text) <= MAX_MESSAGE_LENGTH:
            return [text]
        chunks = []
        while text:
            if len(text) <= MAX_MESSAGE_LENGTH:
                chunks.append(text)
                break
            split_at = text.rfind("\n", 0, MAX_MESSAGE_LENGTH)
            if split_at == -1:
                split_at = MAX_MESSAGE_LENGTH
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks
