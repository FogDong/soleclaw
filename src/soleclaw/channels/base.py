from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from ..bus.events import InboundMessage, OutboundMessage
from ..bus.queue import MessageBus


class BaseChannel(ABC):
    name: str = "base"

    def __init__(self, config: Any, bus: MessageBus):
        self.config = config
        self.bus = bus

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None: ...

    async def send_typing(self, chat_id: str, thread_id: str = "") -> None:
        pass

    async def _handle_message(self, sender_id: str, chat_id: str, content: str) -> None:
        msg = InboundMessage(channel=self.name, sender_id=sender_id, chat_id=chat_id, content=content)
        await self.bus.publish_inbound(msg)
