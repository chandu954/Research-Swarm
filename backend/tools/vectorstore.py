"""Vector database tool using ChromaDB."""
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger


try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    chromadb = None
    Settings = None


DEFAULT_COLLECTION = "research_chunks"
DEFAULT_PERSIST_DIR = "./data/chroma_db"


class VectorStore:
    """Wrapper around ChromaDB for document chunk storage and retrieval."""

    def __init__(
        self,
        persist_directory: str = DEFAULT_PERSIST_DIR,
        collection_name: str = DEFAULT_COLLECTION,
    ):
        if chromadb is None:
            logger.error("chromadb is not installed, vector store unavailable")
            self.client = None
            self.collection = None
            return

        os.makedirs(persist_directory, exist_ok=True)

        try:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False),
            )
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"VectorStore initialized at {persist_directory}, "
                f"collection: {collection_name}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.client = None
            self.collection = None

    def add_chunks(
        self,
        ids: List[str],
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Add document chunks to the vector store.

        Args:
            ids: Unique identifiers for each chunk.
            documents: Text content of each chunk.
            embeddings: Vector embeddings for each chunk.
            metadatas: Optional metadata for each chunk.

        Returns:
            True if successful, False otherwise.
        """
        if not self.collection:
            logger.warning("Collection not available, cannot add chunks")
            return False

        if not (len(ids) == len(documents) == len(embeddings)):
            logger.error(
                f"Mismatched lengths: ids={len(ids)}, docs={len(documents)}, "
                f"embeddings={len(embeddings)}"
            )
            return False

        try:
            self.collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas or [{} for _ in ids],
            )
            logger.info(f"Added {len(ids)} chunks to vector store")
            return True
        except Exception as e:
            logger.error(f"Failed to add chunks to vector store: {e}")
            return False

    def query(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query the vector store for similar chunks.

        Args:
            query_embedding: Vector embedding of the query.
            top_k: Number of results to return.
            where: Optional filter conditions.

        Returns:
            List of result dicts with keys: content, metadata, distance, score.
        """
        if not self.collection:
            logger.warning("Collection not available, cannot query")
            return []

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

            formatted: List[Dict[str, Any]] = []
            for i in range(len(results["documents"][0])):
                distance = results["distances"][0][i] if results.get("distances") else 0.0
                formatted.append({
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": distance,
                    "score": 1.0 - distance,
                })

            logger.info(f"Query returned {len(formatted)} results")
            return formatted

        except Exception as e:
            logger.error(f"Failed to query vector store: {e}")
            return []

    def delete_collection(self) -> bool:
        """Delete the current collection."""
        if not self.client or not self.collection:
            return False

        try:
            self.client.delete_collection(self.collection.name)
            self.collection = None
            logger.info("Collection deleted")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False

    def get_count(self) -> int:
        """Get the number of chunks in the collection."""
        if not self.collection:
            return 0
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Failed to get count: {e}")
            return 0
