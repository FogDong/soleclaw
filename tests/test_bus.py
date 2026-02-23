import asyncio
from soleclaw.bus.events import InboundMessage, OutboundMessage
from soleclaw.bus.queue import MessageBus


def test_inbound_message_session_key():
    msg = InboundMessage(channel="cli", sender_id="user1", chat_id="direct", content="hello")
    assert msg.session_key == "cli:direct"


def test_outbound_message():
    msg = OutboundMessage(channel="cli", chat_id="direct", content="hi back")
    assert msg.content == "hi back"


async def test_bus_publish_consume():
    bus = MessageBus()
    msg = InboundMessage(channel="cli", sender_id="u1", chat_id="d", content="test")
    await bus.publish_inbound(msg)
    got = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
    assert got.content == "test"
