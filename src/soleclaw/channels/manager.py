from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import BaseChannel
from ..bus.queue import MessageBus

log = logging.getLogger(__name__)


class ChannelManager:
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self._channels: dict[str, BaseChannel] = {}
        self._running = False

    def add(self, channel: BaseChannel) -> None:
        self._channels[channel.name] = channel

    async def start_all(self) -> None:
        for name, ch in self._channels.items():
            try:
                await ch.start()
                log.info("Channel %s started", name)
            except Exception:
                log.exception("Failed to start channel %s", name)

    async def stop_all(self) -> None:
        self._running = False
        for name, ch in self._channels.items():
            try:
                await ch.stop()
                log.info("Channel %s stopped", name)
            except Exception:
                log.exception("Failed to stop channel %s", name)

    async def send_typing(self, channel: str, chat_id: str, thread_id: str = "") -> None:
        ch = self._channels.get(channel)
        if ch:
            await ch.send_typing(chat_id, thread_id)

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_outbound(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            ch = self._channels.get(msg.channel)
            if not ch:
                log.warning("No channel %r for outbound message to %s", msg.channel, msg.chat_id)
                continue
            try:
                await ch.send(msg)
            except Exception:
                log.exception("Failed to send outbound on channel %s", msg.channel)

    async def _reaction_loop(self) -> None:
        while self._running:
            try:
                req = await asyncio.wait_for(self.bus.consume_reaction(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            ch = self._channels.get(req.channel)
            if not ch:
                log.warning("No channel %r for reaction", req.channel)
                continue
            try:
                await ch.react(req)
            except Exception:
                log.exception("Failed to send reaction on channel %s", req.channel)

    async def run(self) -> None:
        self._running = True
        await self.start_all()
        log.info("ChannelManager running with %d channel(s)", len(self._channels))
        try:
            await asyncio.gather(self._dispatch_loop(), self._reaction_loop())
        finally:
            await self.stop_all()
