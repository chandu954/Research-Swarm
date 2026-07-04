"""Ollama LLM provider — local models via Ollama API."""
from __future__ import annotations
import os
from typing import Any
from loguru import logger

from backend.llm.base import LLMProvider
from backend.core.plugin import PluginSpec
from backend.models.ollama import OllamaClient, OllamaConfig


class OllamaProvider(LLMProvider):
    spec = PluginSpec(
        name="ollama",
        description="Local LLMs via Ollama",
        version="1.0.0",
        config_schema={"base_url": {"type": "string", "required": False}},
    )

    def __init__(self) -> None:
        self.client: OllamaClient | None = None
        self._config: dict[str, Any] = {}

    async def initialize(self) -> None:
        base_url = self._config.get("base_url") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        config = OllamaConfig(base_url=base_url)
        self.client = OllamaClient(config=config)
        logger.info(f"Ollama provider initialized (base_url={base_url})")

    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        if self.client is None:
            raise RuntimeError("OllamaProvider not initialized — call initialize() first")
        return self.client.generate(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            options=options,
        )

    def create_embedding(self, model: str, text: str) -> list[float]:
        if self.client is None:
            raise RuntimeError("OllamaProvider not initialized — call initialize() first")
        return self.client.create_embedding(model=model, text=text)
