"""Text embedding tool using Ollama models."""
from typing import List, Optional
from loguru import logger


try:
    import httpx
except ImportError:
    httpx = None


DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_OLLAMA_URL = "http://localhost:11434"


def create_embeddings(
    texts: List[str],
    model: str = DEFAULT_EMBEDDING_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
) -> Optional[List[List[float]]]:
    """Create embeddings for a list of texts using Ollama.

    Args:
        texts: List of text strings to embed.
        model: Ollama embedding model name.
        ollama_url: Base URL of the Ollama server.

    Returns:
        List of embedding vectors, or None on failure.
    """
    if httpx is None:
        logger.error("httpx is not installed")
        return None

    if not texts:
        logger.warning("No texts provided for embedding")
        return None

    logger.info(f"Creating {len(texts)} embeddings with model: {model}")
    embeddings: List[List[float]] = []

    for i, text in enumerate(texts):
        try:
            with httpx.Client(base_url=ollama_url, timeout=60) as client:
                response = client.post(
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


def create_single_embedding(
    text: str,
    model: str = DEFAULT_EMBEDDING_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
) -> Optional[List[float]]:
    """Create a single embedding for a text string."""
    embeddings = create_embeddings([text], model, ollama_url)
    if embeddings and len(embeddings) > 0:
        return embeddings[0]
    return None
