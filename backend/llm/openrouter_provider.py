from __future__ import annotations
import json
from typing import Dict, Any, Optional
import httpx
from loguru import logger

from backend.llm.base import LLMProvider
from backend.llm.context import get_openrouter_key


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(LLMProvider):
    def __init__(self):
        self.api_key = get_openrouter_key()
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=60.0)
        return self._client

    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        temperature = 0.2
        max_tokens = 4096
        if options:
            temperature = options.get("temperature", temperature)
            max_tokens = options.get("num_predict", max_tokens)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = self.client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/research-swarm",
                    "X-Title": "ResearchSwarm AI",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPError as e:
            logger.error(f"OpenRouter request failed: {e}")
            raise
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"OpenRouter response parse failed: {e}")
            raise

    def create_embedding(self, model: str, text: str) -> list[float]:
        payload = {"model": model or "text-embedding-3-small", "input": text}

        try:
            response = self.client.post(
                f"{OPENROUTER_BASE_URL}/embeddings",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"OpenRouter embedding failed: {e}")
            return []
