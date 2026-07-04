"""Conversation memory provider wrapping ConversationMemory."""
from __future__ import annotations
import os
from typing import Any
from loguru import logger

from backend.core.plugin import PluginSpec
from backend.core.providers.memory import MemoryProvider

from backend.agents.memory import ConversationMemory


class ConversationMemoryProvider(MemoryProvider):
    spec = PluginSpec(
        name="conversation",
        description="Conversation memory with semantic vector search",
        version="1.0.0",
    )

    def __init__(self) -> None:
        self._memory: ConversationMemory | None = None

    async def initialize(self) -> None:
        memory_dir = os.getenv("MEMORY_DIR", "./data/memory")
        self._memory = ConversationMemory(memory_dir=memory_dir)
        logger.info(f"ConversationMemoryProvider initialized")

    async def cleanup(self) -> None:
        self._memory = None

    async def store(self, key: str, value: Any, tags: list[str] | None = None) -> None:
        if not self._memory:
            raise RuntimeError("ConversationMemoryProvider not initialized")
        self._memory.add_turn(
            conversation_id=key,
            role=tags[0] if tags else "system",
            content=str(value),
            metadata={"tags": tags} if tags else None,
        )

    async def retrieve(self, key: str) -> Any | None:
        if not self._memory:
            return None
        conv = self._memory.get_conversation(key)
        if conv is None:
            return None
        return [{"role": t.role, "content": t.content} for t in conv.turns]

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self._memory:
            return []
        return self._memory.retrieve_semantic(query=query, top_k=limit)

    async def delete(self, key: str) -> bool:
        if not self._memory:
            return False
        return self._memory.delete_conversation(key)
