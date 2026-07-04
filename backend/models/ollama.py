"""Ollama client for connecting to local models."""
from typing import Dict, Any, Optional
import httpx
from loguru import logger

from pydantic import BaseModel, Field


class OllamaConfig(BaseModel):
    """Configuration for Ollama client."""

    base_url: str = Field(default="http://localhost:11434")
    timeout: int = Field(default=30)


class OllamaClient:
    """Client for communicating with Ollama API."""

    def __init__(self, config: Optional[OllamaConfig] = None):
        self.config = config or OllamaConfig()
        self._client: httpx.Client | None = None
        self.models_cache: Optional[list] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(base_url=self.config.base_url, timeout=self.config.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def list_models(self) -> list[Dict[str, Any]]:
        """List available models from Ollama."""
        if self.models_cache:
            return self.models_cache
        try:
            response = self.client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            self.models_cache = data.get("models", [])
            return self.models_cache
        except httpx.HTTPError as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    def generate(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None,
        context: Optional[list] = None,
    ) -> str:
        """Generate text using a model. Returns the full response string."""
        payload: dict = {"model": model, "prompt": prompt, "stream": False}
        if system_prompt:
            payload["system"] = system_prompt
        if options:
            payload["options"] = options
        if context:
            payload["context"] = context

        try:
            response = self.client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except httpx.HTTPError as e:
            logger.error(f"Failed to generate with model {model}: {e}")
            return ""

    def create_embedding(
        self, model: str, text: str, truncate: bool = True
    ) -> list[float]:
        """Create embeddings for text."""
        try:
            response = self.client.post(
                "/api/embeddings",
                json={"model": model, "prompt": text, "truncate": truncate}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to create embedding: {e}")
            return []
