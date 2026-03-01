from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from .base import BaseChannel
from ..bus.queue import MessageBus
from ..bus.events import InboundMessage, ReactionRequest

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 3000


def _markdown_to_mrkdwn(text: str) -> str:
    """Convert standard markdown to Slack mrkdwn format."""
    if not text:
        return ""
    text = re.sub(r'```(\w*)\n?([\s\S]*?)```', r'```\2```', text)
    text = re.sub(r'#{1,6}\s+(.+)', r'*\1*', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', text)
    text = re.sub(r'(?<!\*)\*\*(.+?)\*\*(?!\*)', r'*\1*', text)
    text = re.sub(r'(?<!_)__(.+?)__(?!_)', r'*\1*', text)
    text = re.sub(r'~~(.+?)~~', r'~\1~', text)
    return text


class SlackChannel(BaseChannel):
    name = "slack"

    def __init__(
        self, bus: MessageBus, bot_token: str, app_token: str,
        watch_channels: list[str], allowed_users: list[str],
    ):
        super().__init__(config=None, bus=bus)
        self._bot_token = bot_token
        self._app_token = app_token
        self._watch_channels = set(watch_channels) if watch_channels else set()
        self._allowed_users = set(allowed_users) if allowed_users else set()
        self._bolt_app: Any = None
        self._handler: Any = None

    def _is_allowed(self, user_id: str) -> bool:
        if not self._allowed_users:
            return True
        return user_id in self._allowed_users

    def _is_watched(self, channel_id: str) -> bool:
        if not self._watch_channels:
            return True
        return channel_id in self._watch_channels

    async def start(self) -> None:
        from slack_bolt.async_app import AsyncApp
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        self._bolt_app = AsyncApp(token=self._bot_token)

        @self._bolt_app.event("message")
        async def _on_message(event: dict, say: Any) -> None:
            if event.get("subtype"):
                return
            channel_id = event.get("channel", "")
            user_id = event.get("user", "")
            text = event.get("text", "")
            if not text or not user_id:
                return
            if not self._is_watched(channel_id):
                return
            if not self._is_allowed(user_id):
                return

            thread_ts = event.get("thread_ts", "")
            message_ts = event.get("ts", "")
            logger.debug("Slack inbound: channel=%s user=%s text=%s", channel_id, user_id, text[:100])

            msg = InboundMessage(
                channel=self.name, sender_id=user_id, chat_id=channel_id,
                content=text, thread_id=thread_ts or message_ts,
                metadata={"message_ts": message_ts},
            )
            await self.bus.publish_inbound(msg)

        self._handler = AsyncSocketModeHandler(self._bolt_app, self._app_token)
        await self._handler.connect_async()
        logger.info("Slack channel started (watching %d channel(s))", len(self._watch_channels))

    async def stop(self) -> None:
        if self._handler:
            await self._handler.close_async()

    async def send(self, msg: Any) -> None:
        if not self._bolt_app:
            return
        text = _markdown_to_mrkdwn(msg.content)
        chunks = self._split_message(text)
        kwargs: dict[str, Any] = {"channel": msg.chat_id}
        if msg.thread_id:
            kwargs["thread_ts"] = msg.thread_id
        for chunk in chunks:
            try:
                await self._bolt_app.client.chat_postMessage(text=chunk, **kwargs)
            except Exception:
                logger.exception("Failed to send Slack message to %s", msg.chat_id)

    async def react(self, req: ReactionRequest) -> None:
        if not self._bolt_app:
            return
        emoji = req.emoji.strip(":")
        try:
            await self._bolt_app.client.reactions_add(
                channel=req.chat_id, name=emoji, timestamp=req.message_ts,
            )
        except Exception:
            logger.exception("Failed to add reaction %s", emoji)

    async def send_typing(self, chat_id: str, thread_id: str = "") -> None:
        pass

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
