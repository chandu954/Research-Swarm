"""Ollama client for connecting to local models."""
import asyncio
import json
from typing import Dict, Any, Optional, Iterator
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
        self.client = httpx.Client(base_url=self.config.base_url, timeout=self.config.timeout)
        self.models_cache: Optional[list] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    async def list_models(self) -> list[Dict[str, Any]]:
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

    async def pull_model(self, model_name: str) -> Iterator[Dict[str, Any]]:
        """Pull a model from Ollama."""
        try:
            response = self.client.post(
                "/api/pull", 
                json={"name": model_name}, 
                stream=True
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        pass
        except httpx.HTTPError as e:
            logger.error(f"Failed to pull model {model_name}: {e}")

    async def generate(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None,
        context: Optional[list] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Generate text using a model."""
        payload = {"model": model, "prompt": prompt, "stream": stream}
        if system_prompt:
            payload["system"] = system_prompt
        if options:
            payload["options"] = options
        if context:
            payload["context"] = context

        try:
            response = self.client.post("/api/generate", json=payload, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        pass
        except httpx.HTTPError as e:
            logger.error(f"Failed to generate with model {model}: {e}")

    async def create_embedding(
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
