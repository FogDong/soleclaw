from __future__ import annotations

from ..bus.events import OutboundMessage
from ..bus.queue import MessageBus
from .base import BaseChannel


class CLIChannel(BaseChannel):
    name = "cli"

    def __init__(self, bus: MessageBus):
        super().__init__(config=None, bus=bus)

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send(self, msg: OutboundMessage) -> None:
        print(f"\n{msg.content}\n")
