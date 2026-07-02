"""Conversation memory with semantic vector search for multi-turn research."""
from __future__ import annotations
import json
import os
import time
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field, asdict
from loguru import logger


MEMORY_DIR = "./data/memory"
SEMANTIC_MEMORY_COLLECTION = "conversation_memories"

try:
    import chromadb
    from chromadb.config import Settings
    has_chromadb = True
except ImportError:
    chromadb = None
    has_chromadb = False

try:
    import httpx
    has_httpx = True
except ImportError:
    httpx = None
    has_httpx = False


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    """A full conversation session."""

    conversation_id: str
    turns: List[ConversationTurn] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationMemory:
    """Persistent conversation memory backed by local JSON files."""

    def __init__(self, memory_dir: str = MEMORY_DIR):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Conversation] = {}
        logger.info(f"ConversationMemory initialized at {memory_dir}")

    def create_conversation(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new conversation and return its ID."""
        conv_id = str(uuid.uuid4())
        conv = Conversation(
            conversation_id=conv_id,
            metadata=metadata or {},
        )
        self._cache[conv_id] = conv
        self._persist(conv)
        logger.info(f"Created conversation: {conv_id}")
        return conv_id

    def get_history(
        self,
        conversation_id: str,
        max_turns: int = 10,
    ) -> List[Dict[str, str]]:
        """Get recent turns as a list of {role, content} dicts."""
        conv = self._load(conversation_id)
        if not conv:
            return []

        recent = conv.turns[-max_turns:]
        return [{"role": t.role, "content": t.content} for t in recent]

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get full conversation object."""
        return self._load(conversation_id)

    def add_turn(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        conv = self._load(conversation_id)
        if not conv:
            conv = Conversation(conversation_id=conversation_id)
            self._cache[conversation_id] = conv

        turn = ConversationTurn(role=role, content=content, metadata=metadata or {})
        conv.turns.append(turn)
        conv.updated_at = time.time()
        self._persist(conv)

        self._store_semantic_memory(conversation_id, role, content, metadata)

    def retrieve_semantic(
        self,
        query: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Retrieve semantically similar past conversation turns."""
        if not has_chromadb or not has_httpx:
            return []

        collection = self._ensure_semantic_collection()
        if collection is None:
            return []

        query_embedding = self._create_embedding(query)
        if not query_embedding:
            return []

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            if not results or not results.get("documents"):
                return []

            memories = []
            for i in range(len(results["documents"][0])):
                distance = results["distances"][0][i] if results.get("distances") else 0.0
                memories.append({
                    "content": results["documents"][0][i],
                    "role": results["metadatas"][0][i].get("role", "unknown"),
                    "conversation_id": results["metadatas"][0][i].get("conversation_id", ""),
                    "similarity": 1.0 - distance,
                    "timestamp": results["metadatas"][0][i].get("timestamp", 0),
                })

            logger.debug(f"Retrieved {len(memories)} semantic memories for: {query[:60]}...")
            return memories
        except Exception as e:
            logger.error(f"Semantic memory query failed: {e}")
            return []

    def _ensure_semantic_collection(self):
        """Get or create the ChromaDB collection for semantic memories."""
        if not has_chromadb:
            return None

        persist_dir = str(self.memory_dir / "chroma")
        try:
            client = chromadb.PersistentClient(
                path=persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            return client.get_or_create_collection(
                name=SEMANTIC_MEMORY_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            logger.error(f"Failed to create semantic memory collection: {e}")
            return None

    @staticmethod
    def _create_embedding(text: str) -> Optional[List[float]]:
        """Create an embedding using Ollama's nomic-embed-text."""
        if not has_httpx:
            return None

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            with httpx.Client(base_url=base_url, timeout=30) as client:
                resp = client.post(
                    "/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": text[:2048], "truncate": True},
                )
                resp.raise_for_status()
                return resp.json().get("embedding")
        except Exception as e:
            logger.debug(f"Embedding failed (non-critical): {e}")
            return None

    def _store_semantic_memory(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Embed and store a conversation turn for semantic retrieval."""
        if not content or len(content) < 20:
            return

        embedding = self._create_embedding(content)
        if not embedding:
            return

        collection = self._ensure_semantic_collection()
        if collection is None:
            return

        memory_id = str(uuid.uuid4())
        try:
            collection.add(
                ids=[memory_id],
                documents=[content[:2000]],
                embeddings=[embedding],
                metadatas=[{
                    "conversation_id": conversation_id,
                    "role": role,
                    "timestamp": time.time(),
                    "source": metadata.get("source", "chat") if metadata else "chat",
                }],
            )
        except Exception as e:
            logger.warning(f"Failed to store semantic memory: {e}")

    def list_conversations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent conversations."""
        convs = []
        for p in sorted(self.memory_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:limit]:
            try:
                data = json.loads(p.read_text())
                convs.append({
                    "conversation_id": data.get("conversation_id", p.stem),
                    "turn_count": len(data.get("turns", [])),
                    "updated_at": data.get("updated_at", 0),
                    "created_at": data.get("created_at", 0),
                    "first_query": data["turns"][0]["content"][:100] if data.get("turns") else "",
                })
            except Exception as e:
                logger.warning(f"Failed to load conversation {p.name}: {e}")
        return convs

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        path = self.memory_dir / f"{conversation_id}.json"
        if path.exists():
            path.unlink()
        self._cache.pop(conversation_id, None)
        return True

    def _persist(self, conv: Conversation) -> None:
        """Save conversation to disk."""
        path = self.memory_dir / f"{conv.conversation_id}.json"
        try:
            path.write_text(json.dumps(asdict(conv), indent=2, default=str))
        except Exception as e:
            logger.error(f"Failed to persist conversation {conv.conversation_id}: {e}")

    def _load(self, conversation_id: str) -> Optional[Conversation]:
        """Load conversation from cache or disk."""
        if conversation_id in self._cache:
            return self._cache[conversation_id]

        path = self.memory_dir / f"{conversation_id}.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            conv = Conversation(
                conversation_id=data["conversation_id"],
                turns=[ConversationTurn(**t) for t in data.get("turns", [])],
                created_at=data.get("created_at", 0),
                updated_at=data.get("updated_at", 0),
                metadata=data.get("metadata", {}),
            )
            self._cache[conversation_id] = conv
            return conv
        except Exception as e:
            logger.error(f"Failed to load conversation {conversation_id}: {e}")
            return None


# Module-level singleton
_memory: Optional[ConversationMemory] = None


def get_memory() -> ConversationMemory:
    """Get or create the global memory singleton."""
    global _memory
    if _memory is None:
        _memory = ConversationMemory()
    return _memory
