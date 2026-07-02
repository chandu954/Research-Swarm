from __future__ import annotations
import json
from typing import Dict, Any, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError
from loguru import logger

from backend.llm.base import LLMProvider
from backend.llm.context import get_openrouter_key


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(LLMProvider):
    def __init__(self):
        self.api_key = get_openrouter_key()
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")

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

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode()

        req = Request(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/research-swarm",
                "X-Title": "ResearchSwarm AI",
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
        except URLError as e:
            logger.error(f"OpenRouter request failed: {e}")
            raise
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"OpenRouter response parse failed: {e}")
            raise

    def create_embedding(self, model: str, text: str) -> list[float]:
        payload = json.dumps({
            "model": model or "text-embedding-3-small",
            "input": text,
        }).encode()

        req = Request(
            f"{OPENROUTER_BASE_URL}/embeddings",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            return data["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"OpenRouter embedding failed: {e}")
            return []
