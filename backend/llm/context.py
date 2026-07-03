from __future__ import annotations
import os
from contextvars import ContextVar, Token
from typing import Optional

_llm_provider: ContextVar[str] = ContextVar("_llm_provider", default="")
_planner_model: ContextVar[str] = ContextVar("_planner_model", default="")
_research_model: ContextVar[str] = ContextVar("_research_model", default="")
_document_model: ContextVar[str] = ContextVar("_document_model", default="")
_answer_model: ContextVar[str] = ContextVar("_answer_model", default="")
_openrouter_key: ContextVar[str] = ContextVar("_openrouter_key", default="")


def get_llm_provider() -> str:
    val = _llm_provider.get()
    return val or os.getenv("LLM_PROVIDER", "ollama")


def get_openrouter_key() -> Optional[str]:
    val = _openrouter_key.get()
    return val or os.getenv("OPENROUTER_API_KEY")


def get_planner_model() -> str:
    val = _planner_model.get()
    return val or os.getenv("PLANNER_MODEL", "qwen3:14b")


def get_research_model() -> str:
    val = _research_model.get()
    return val or os.getenv("RESEARCH_MODEL", "qwen3:14b")


def get_document_model() -> str:
    val = _document_model.get()
    return val or os.getenv("DOCUMENT_MODEL", "qwen3:14b")


def get_answer_model() -> str:
    val = _answer_model.get()
    return val or os.getenv("ANSWER_MODEL", "qwen3:14b")


class ProviderOverrides:
    def __init__(self) -> None:
        self._entries: list[tuple[ContextVar, Token]] = []

    def apply(
        self,
        llm_provider: Optional[str] = None,
        planner_model: Optional[str] = None,
        research_model: Optional[str] = None,
        document_model: Optional[str] = None,
        answer_model: Optional[str] = None,
        openrouter_key: Optional[str] = None,
    ) -> None:
        if llm_provider is not None:
            self._entries.append((_llm_provider, _llm_provider.set(llm_provider)))
        if planner_model is not None:
            self._entries.append((_planner_model, _planner_model.set(planner_model)))
        if research_model is not None:
            self._entries.append((_research_model, _research_model.set(research_model)))
        if document_model is not None:
            self._entries.append((_document_model, _document_model.set(document_model)))
        if answer_model is not None:
            self._entries.append((_answer_model, _answer_model.set(answer_model)))
        if openrouter_key is not None:
            self._entries.append((_openrouter_key, _openrouter_key.set(openrouter_key)))

    def restore(self) -> None:
        for var, token in reversed(self._entries):
            try:
                var.reset(token)
            except (ValueError, LookupError):
                pass
        self._entries.clear()
