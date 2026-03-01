from unittest.mock import AsyncMock, MagicMock, patch

from soleclaw.channels.slack import SlackChannel, _markdown_to_mrkdwn
from soleclaw.bus.queue import MessageBus
from soleclaw.bus.events import OutboundMessage, ReactionRequest


def test_slack_channel_init():
    bus = MessageBus()
    ch = SlackChannel(
        bus=bus, bot_token="xoxb-fake", app_token="xapp-fake",
        watch_channels=["C123"], allowed_users=["U456"],
    )
    assert ch.name == "slack"
    assert ch._watch_channels == {"C123"}
    assert ch._allowed_users == {"U456"}


def test_slack_user_filtering():
    bus = MessageBus()
    ch = SlackChannel(
        bus=bus, bot_token="xoxb-fake", app_token="xapp-fake",
        watch_channels=[], allowed_users=["U456"],
    )
    assert ch._is_allowed("U456") is True
    assert ch._is_allowed("U999") is False


def test_slack_empty_allowlist_allows_all():
    bus = MessageBus()
    ch = SlackChannel(
        bus=bus, bot_token="xoxb-fake", app_token="xapp-fake",
        watch_channels=[], allowed_users=[],
    )
    assert ch._is_allowed("anyone") is True


def test_slack_channel_filtering():
    bus = MessageBus()
    ch = SlackChannel(
        bus=bus, bot_token="xoxb-fake", app_token="xapp-fake",
        watch_channels=["C123"], allowed_users=[],
    )
    assert ch._is_watched("C123") is True
    assert ch._is_watched("C999") is False


def test_slack_empty_channel_list_watches_all():
    bus = MessageBus()
    ch = SlackChannel(
        bus=bus, bot_token="xoxb-fake", app_token="xapp-fake",
        watch_channels=[], allowed_users=[],
    )
    assert ch._is_watched("anything") is True


def test_markdown_to_mrkdwn_bold():
    assert _markdown_to_mrkdwn("**bold**") == "*bold*"


def test_markdown_to_mrkdwn_link():
    assert _markdown_to_mrkdwn("[text](http://example.com)") == "<http://example.com|text>"


def test_markdown_to_mrkdwn_strikethrough():
    assert _markdown_to_mrkdwn("~~deleted~~") == "~deleted~"


def test_markdown_to_mrkdwn_heading():
    assert _markdown_to_mrkdwn("## Title") == "*Title*"


def test_split_message():
    ch = SlackChannel(
        bus=MessageBus(), bot_token="x", app_token="x",
        watch_channels=[], allowed_users=[],
    )
    short = "hello"
    assert ch._split_message(short) == ["hello"]

    long_text = "a" * 4000
    chunks = ch._split_message(long_text)
    assert len(chunks) == 2
    assert "".join(chunks) == long_text


async def test_slack_send():
    bus = MessageBus()
    ch = SlackChannel(
        bus=bus, bot_token="xoxb-fake", app_token="xapp-fake",
        watch_channels=[], allowed_users=[],
    )
    mock_client = AsyncMock()
    mock_app = MagicMock()
    mock_app.client = mock_client
    ch._bolt_app = mock_app

    msg = OutboundMessage(channel="slack", chat_id="C123", content="hello", thread_id="1234.5678")
    await ch.send(msg)

    mock_client.chat_postMessage.assert_called_once_with(
        text="hello", channel="C123", thread_ts="1234.5678",
    )


async def test_slack_react():
    bus = MessageBus()
    ch = SlackChannel(
        bus=bus, bot_token="xoxb-fake", app_token="xapp-fake",
        watch_channels=[], allowed_users=[],
    )
    mock_client = AsyncMock()
    mock_app = MagicMock()
    mock_app.client = mock_client
    ch._bolt_app = mock_app

    req = ReactionRequest(channel="slack", chat_id="C123", emoji=":thumbsup:", message_ts="1234.5678")
    await ch.react(req)

    mock_client.reactions_add.assert_called_once_with(
        channel="C123", name="thumbsup", timestamp="1234.5678",
    )
