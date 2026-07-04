"""ChromaDB vector store — concrete VectorDBProvider implementation."""
from __future__ import annotations
import os
from typing import Any
from loguru import logger

try:
    import chromadb
    try:
        from chromadb import Settings
    except ImportError:
        try:
            from chromadb.config import Settings
        except ImportError:
            Settings = None
except ImportError:
    chromadb = None
    Settings = None

from backend.core.plugin import PluginSpec
from backend.core.providers.vector_db import VectorDBProvider


DEFAULT_PERSIST_DIR = "./data/chroma_db"
DEFAULT_COLLECTION = "research_chunks"


class ChromaDBVectorStore(VectorDBProvider):
    spec = PluginSpec(
        name="chromadb",
        description="ChromaDB vector store for document chunks",
        version="1.0.0",
    )

    def __init__(self) -> None:
        self._client: chromadb.PersistentClient | None = None
        self._collection = None
        self._persist_directory: str = ""
        self._collection_name: str = ""

    async def initialize(self) -> None:
        if chromadb is None:
            logger.error("chromadb not installed, vector store unavailable")
            return
        self._persist_directory = os.getenv("CHROMA_PERSIST_DIR", DEFAULT_PERSIST_DIR)
        self._collection_name = os.getenv("CHROMA_COLLECTION", DEFAULT_COLLECTION)
        os.makedirs(self._persist_directory, exist_ok=True)
        try:
            self._client = chromadb.PersistentClient(
                path=self._persist_directory,
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"ChromaDBVectorStore initialized at {self._persist_directory}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")

    async def cleanup(self) -> None:
        self._client = None
        self._collection = None

    async def store(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        if not self._collection:
            logger.warning("Collection not available, cannot store")
            return
        try:
            self._collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas or [{} for _ in ids],
            )
            logger.info(f"Stored {len(ids)} chunks in vector store")
        except Exception as e:
            logger.error(f"Failed to store chunks: {e}")

    async def query(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self._collection:
            logger.warning("Collection not available, cannot query")
            return []
        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter,
                include=["documents", "metadatas", "distances"],
            )
            formatted: list[dict[str, Any]] = []
            for i in range(len(results["documents"][0])):
                distance = results["distances"][0][i] if results.get("distances") else 0.0
                formatted.append({
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": distance,
                    "score": 1.0 - distance,
                })
            return formatted
        except Exception as e:
            logger.error(f"Vector store query failed: {e}")
            return []

    async def delete(self, ids: list[str]) -> None:
        if not self._collection:
            return
        try:
            self._collection.delete(ids=ids)
        except Exception as e:
            logger.error(f"Vector store delete failed: {e}")
