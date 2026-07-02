from __future__ import annotations
import os
from typing import Dict, Any, Optional
from loguru import logger

from backend.llm.base import LLMProvider
from backend.models.ollama import OllamaClient, OllamaConfig


class OllamaProvider(LLMProvider):
    def __init__(self):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        config = OllamaConfig(base_url=base_url)
        self.client = OllamaClient(config=config)

    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        raw = ""
        for chunk in self.client.generate(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            options=options,
        ):
            if "response" in chunk:
                raw += chunk["response"]
        return raw.strip()

    def create_embedding(self, model: str, text: str) -> list[float]:
        return self.client.create_embedding(model=model, text=text)
