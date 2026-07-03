"""Text embedding tool using Ollama models — with shared httpx client."""
from typing import List, Optional
from loguru import logger


try:
    import httpx
except ImportError:
    httpx = None


DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_OLLAMA_URL = "http://localhost:11434"


class EmbeddingClient:
    """Reusable embedding client that shares a single httpx session."""

    def __init__(self, ollama_url: str = DEFAULT_OLLAMA_URL):
        self.ollama_url = ollama_url
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(base_url=self.ollama_url, timeout=60)
        return self._client

    def embed(self, texts: List[str], model: str = DEFAULT_EMBEDDING_MODEL) -> Optional[List[List[float]]]:
        if httpx is None:
            logger.error("httpx is not installed")
            return None
        if not texts:
            logger.warning("No texts provided for embedding")
            return None
        embeddings: List[List[float]] = []
        for i, text in enumerate(texts):
            try:
                response = self.client.post(
                    "/api/embeddings",
                    json={"model": model, "prompt": text, "truncate": True},
                )
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding")
                if embedding:
                    embeddings.append(embedding)
                    if (i + 1) % 10 == 0:
                        logger.info(f"Embedded {i + 1}/{len(texts)} texts")
            except Exception as e:
                logger.error(f"Failed to create embedding for text {i}: {e}")
                embeddings.append([0.0] * 768)
        logger.info(f"Successfully created {len(embeddings)} embeddings")
        return embeddings if embeddings else None

    def close(self):
        if self._client:
            self._client.close()
            self._client = None


_embedding_client: Optional[EmbeddingClient] = None


def get_embedding_client() -> EmbeddingClient:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client


def create_embeddings(
    texts: List[str],
    model: str = DEFAULT_EMBEDDING_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
) -> Optional[List[List[float]]]:
    if httpx is None:
        logger.error("httpx is not installed")
        return None
    client = EmbeddingClient(ollama_url)
    try:
        return client.embed(texts, model)
    finally:
        client.close()


def create_single_embedding(
    text: str,
    model: str = DEFAULT_EMBEDDING_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
) -> Optional[List[float]]:
    embeddings = create_embeddings([text], model, ollama_url)
    if embeddings and len(embeddings) > 0:
        return embeddings[0]
    return None
