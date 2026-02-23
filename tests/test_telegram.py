from unittest.mock import AsyncMock, MagicMock

from soleclaw.channels.telegram import TelegramChannel
from soleclaw.bus.queue import MessageBus
from soleclaw.bus.events import InboundMessage


def test_telegram_channel_init():
    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake:token", allowed_users=["alice"])
    assert ch.name == "telegram"
    assert ch._allowed_users == {"alice"}


def test_telegram_channel_user_filtering():
    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake:token", allowed_users=["alice"])
    assert ch._is_allowed("alice") is True
    assert ch._is_allowed("bob") is False


def test_telegram_channel_empty_allowlist_allows_all():
    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake:token", allowed_users=[])
    assert ch._is_allowed("anyone") is True


async def test_telegram_channel_inbound():
    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake:token", allowed_users=[])

    update = MagicMock()
    update.effective_user.username = "alice"
    update.effective_chat.id = 123
    update.message.text = "hello"
    update.message.reply_to_message = None

    context = MagicMock()
    context.bot.send_message = AsyncMock()

    await ch._handle_tg_message(update, context)

    msg = await bus.consume_inbound()
    assert isinstance(msg, InboundMessage)
    assert msg.content == "hello"
    assert msg.channel == "telegram"
    assert msg.chat_id == "123"
    assert msg.sender_id == "alice"


def test_telegram_markdown_to_html():
    from soleclaw.channels.telegram import _markdown_to_html

    assert _markdown_to_html("Hello **bold**") == "Hello <b>bold</b>"
    assert _markdown_to_html("`code`") == "<code>code</code>"
    assert _markdown_to_html("~~strike~~") == "<s>strike</s>"
    assert "<pre><code>" in _markdown_to_html("```\nprint(1)\n```")
    assert _markdown_to_html("a < b & c") == "a &lt; b &amp; c"
    assert _markdown_to_html("") == ""
