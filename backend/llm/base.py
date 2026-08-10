"""LLM provider base — extends core provider with streaming support."""
from __future__ import annotations
from collections.abc import Generator
from typing import Any, Optional, TYPE_CHECKING

from loguru import logger

from backend.llm.retry import (
    ProviderUnavailableError,
    with_retry,
)
from backend.core.providers.llm import LLMProvider as CoreLLMProvider
from backend.core.plugin import PluginSpec

if TYPE_CHECKING:  # pragma: no cover - runtime import cycles avoided
    from backend.llm.base import LLMProvider as _Base


class LLMProvider(CoreLLMProvider):
    spec: PluginSpec

    # ── Retry-aware generate ──────────────────────────────────────
    # Subclasses implement the raw single-attempt call in
    # ``_generate_once``; ``generate`` wraps it with bounded
    # exponential-backoff retries and, when multiple LLM providers are
    # registered, falls back to an alternate provider after retries are
    # exhausted on the primary.

    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        """Generate text with bounded retry + optional provider fallback."""
        try:
            return with_retry(
                lambda: self._generate_once(prompt, model, system_prompt, options),
                provider=self.spec.name,
                model=model,
            )
        except ProviderUnavailableError as exc:
            alternate = _alternate_llm_provider(self)
            if alternate is None:
                raise
            logger.warning(
                f"{self.spec.name} exhausted ({exc}); trying alternate "
                f"provider {alternate.spec.name}"
            )
            try:
                return with_retry(
                    lambda: alternate._generate_once(prompt, model, system_prompt, options),
                    provider=alternate.spec.name,
                    model=model,
                )
            except ProviderUnavailableError as alt_exc:
                raise ProviderUnavailableError(
                    f"{self.spec.name}/{alternate.spec.name}",
                    model,
                    f"{exc.cause}; {alt_exc.cause}",
                ) from alt_exc

    def _generate_once(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError

    def generate_stream(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> Generator[str, None, None]:
        raise NotImplementedError

    def create_embedding(self, model: str, text: str) -> list[float]:
        raise NotImplementedError


def _alternate_llm_provider(current: "LLMProvider") -> Optional["LLMProvider"]:
    """Return another registered LLM provider (different from ``current``).

    Only providers whose declared config contract is satisfied are
    eligible, so an unconfigured cloud provider is never chosen. Returns
    None when no alternative exists.

    The "llm" type bucket is iterated directly (not ``_plugins``): the
    registry's flat name→plugin map can be shadowed by same-named plugins
    of other types (e.g. the embedding provider also named "ollama").
    """
    try:
        from backend.core.registry import get_plugin_registry
    except Exception:  # pragma: no cover - defensive
        return None
    registry = get_plugin_registry()
    for candidate in registry._by_type.get("llm", {}).values():
        if candidate is None or candidate is current:
            continue
        # Only retry-aware base providers can take over a generate() call.
        if not hasattr(candidate, "_generate_once"):
            continue
        if not candidate.is_configured():
            continue
        return candidate
    return None