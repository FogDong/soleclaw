import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from soleclaw.bus.queue import MessageBus
from soleclaw.bus.events import OutboundMessage
from soleclaw.channels.base import BaseChannel
from soleclaw.channels.manager import ChannelManager


class FakeChannel(BaseChannel):
    name = "fake"

    def __init__(self, bus: MessageBus):
        super().__init__(config=None, bus=bus)
        self.started = False
        self.stopped = False
        self.sent: list[OutboundMessage] = []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def send(self, msg: OutboundMessage) -> None:
        self.sent.append(msg)


def test_add_channel():
    bus = MessageBus()
    mgr = ChannelManager(bus)
    ch = FakeChannel(bus)
    mgr.add(ch)
    assert "fake" in mgr._channels


async def test_start_and_stop_all():
    bus = MessageBus()
    mgr = ChannelManager(bus)
    ch = FakeChannel(bus)
    mgr.add(ch)

    await mgr.start_all()
    assert ch.started

    await mgr.stop_all()
    assert ch.stopped


async def test_dispatch_routes_to_correct_channel():
    bus = MessageBus()
    mgr = ChannelManager(bus)
    ch = FakeChannel(bus)
    mgr.add(ch)

    msg = OutboundMessage(channel="fake", chat_id="123", content="hello")
    await bus.publish_outbound(msg)

    mgr._running = True
    task = asyncio.create_task(mgr._dispatch_loop())
    await asyncio.sleep(0.1)
    mgr._running = False
    await task

    assert len(ch.sent) == 1
    assert ch.sent[0].content == "hello"


async def test_dispatch_ignores_unknown_channel():
    bus = MessageBus()
    mgr = ChannelManager(bus)

    msg = OutboundMessage(channel="nonexistent", chat_id="123", content="hello")
    await bus.publish_outbound(msg)

    mgr._running = True
    task = asyncio.create_task(mgr._dispatch_loop())
    await asyncio.sleep(0.1)
    mgr._running = False
    await task
    # should not raise


async def test_run_starts_channels_and_dispatches():
    bus = MessageBus()
    mgr = ChannelManager(bus)
    ch = FakeChannel(bus)
    mgr.add(ch)

    msg = OutboundMessage(channel="fake", chat_id="456", content="world")
    await bus.publish_outbound(msg)

    task = asyncio.create_task(mgr.run())
    await asyncio.sleep(0.1)
    mgr._running = False
    await task

    assert ch.started
    assert ch.stopped
    assert len(ch.sent) == 1
    assert ch.sent[0].chat_id == "456"
