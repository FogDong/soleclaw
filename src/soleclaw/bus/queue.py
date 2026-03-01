from __future__ import annotations
import asyncio
from .events import InboundMessage, OutboundMessage, ReactionRequest


class MessageBus:
    def __init__(self) -> None:
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self.reactions: asyncio.Queue[ReactionRequest] = asyncio.Queue()

    async def publish_inbound(self, msg: InboundMessage) -> None:
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        await self.outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        return await self.outbound.get()

    async def publish_reaction(self, req: ReactionRequest) -> None:
        await self.reactions.put(req)

    async def consume_reaction(self) -> ReactionRequest:
        return await self.reactions.get()
