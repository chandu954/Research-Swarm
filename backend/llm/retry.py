"""Bounded retry with exponential backoff for LLM provider calls.

Transient upstream failures (HTTP 429/5xx, provider timeouts, connection
resets, upstream quota-"ResourceExhausted" responses) are retried with
jittered exponential backoff, honoring ``Retry-After`` when the upstream
sends it. Permanent failures (auth, unknown model, malformed request) are
never retried. Retries are bounded so a dead provider fails fast with a
``ProviderUnavailableError`` that agents can surface as a terminal state.

Retry policy is tuned via env (optional):
  LLM_RETRY_MAX_ATTEMPTS  (default 3)
  LLM_RETRY_BASE_DELAY    (default 1.0 seconds)

No API keys or credentials ever appear in log lines here.
"""
from __future__ import annotations

import os
import random
import time
from typing import Any, Callable

import httpx
from loguru import logger

MAX_ATTEMPTS = max(1, int(os.getenv("LLM_RETRY_MAX_ATTEMPTS", "3")))
BASE_DELAY = max(0.1, float(os.getenv("LLM_RETRY_BASE_DELAY", "1.0")))
MAX_DELAY = 8.0

# Statuses that indicate a transient upstream condition. 408 is included:
# the request timed out at the provider and may succeed on a fresh attempt.
TRANSIENT_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

# Upstreams report quota exhaustion through 2xx/4xx/5xx bodies (OpenRouter
# proxies Nvidia et al: "ResourceExhausted: Worker local total request
# limit reached"). These markers make any status transient.
EXHAUSTION_MARKERS = (
    "resourceexhausted",
    "resource exhausted",
    "quota exceeded",
    "quota_exceeded",
    "rate limit exceeded",
    "too many requests",
    "overloaded",
    "temporarily unavailable",
)


class ProviderUnavailableError(Exception):
    """A transient upstream failure that survived all retries.

    The message is deliberately operator/user-safe: provider + model +
    a short cause phrase, never credentials or full stack traces.
    """

    def __init__(self, provider: str, model: str, cause: str) -> None:
        self.provider = provider
        self.model = model
        self.cause = cause
        super().__init__(
            f"AI provider {provider!r} is temporarily unavailable "
            f"(model {model!r}): {cause}"
        )


class ProviderConfigError(Exception):
    """Permanent failure — auth, unknown model, malformed request.

    Never retried (it will keep failing the same way).
    """

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"AI provider {provider!r} rejected the request: {message}")


def _body_text(exc: Exception) -> str:
    """Extract a short upstream response body for classification."""
    response = getattr(exc, "response", None)
    if response is None:
        return ""
    try:
        return response.text[:2000] or ""
    except Exception:  # pragma: no cover - defensive
        return ""


def classify_exception(exc: Exception) -> str | None:
    """Classify an exception as "transient", "permanent", or None (retry nothing).

    - transient: retry with backoff (429, 5xx, timeouts, resets, quota bodies)
    - permanent: fail immediately (4xx auth/validation, unknown model)
    - None: unclassifiable — re-raise untouched (agent fallbacks handle it)
    """
    if isinstance(exc, (ProviderConfigError,)):
        return "permanent"
    if isinstance(exc, (ProviderUnavailableError,)):
        return "transient"

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        body = exc.response.text or ""

        if status in TRANSIENT_STATUSES:
            return "transient"
        # Exhaustion markers take priority over the 4xx catch-all: a quota
        # body means the provider is health-impaired, not that our request
        # is malformed — retry it.
        if 400 <= status < 600 and any(m in body.lower() for m in EXHAUSTION_MARKERS):
            return "transient"
        if status == 401 or status == 403:
            return "permanent"
        if status == 404:
            return "permanent"  # unknown model / endpoint — retrying won't help
        if 400 <= status < 500:
            return "permanent"
        if status >= 500:
            return "transient"
        return None

    if isinstance(exc, httpx.TimeoutException):
        return "transient"
    if isinstance(exc, httpx.ConnectError):
        return "transient"
    if isinstance(exc, httpx.NetworkError):
        return "transient"
    if isinstance(exc, httpx.RemoteProtocolError):
        return "transient"
    if isinstance(exc, httpx.ReadError):
        return "transient"

    if isinstance(exc, TimeoutError):
        return "transient"
    if isinstance(exc, ConnectionError):
        return "transient"
    if isinstance(exc, OSError):
        return "transient"

    message = f"{exc}".lower()
    if any(m in message for m in EXHAUSTION_MARKERS):
        return "transient"
    return None


def retry_after_seconds(exc: Exception) -> float | None:
    """Respect an upstream ``Retry-After`` header (seconds or HTTP date)."""
    response = getattr(exc, "response", None)
    if response is None:
        return None
    value = response.headers.get("Retry-After")
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        from email.utils import parsedate_to_datetime

        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            from datetime import timezone as _tz

            parsed = parsed.replace(tzinfo=_tz.utc)
        wait = parsed.timestamp() - time.time()
        return max(0.0, wait)
    except (ValueError, TypeError):
        return None


def _backoff_delay(attempt: int, retry_after: float | None) -> float:
    """Exponential backoff with jitter; Retry-After wins when present."""
    if retry_after is not None:
        return max(retry_after, 0.2)
    delay = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
    return delay + random.uniform(0.0, 0.4)


def _fmt_attempt(provider: str, model: str, attempt: int, max_attempts: int) -> str:
    return f"AI provider {provider!r} (model {model!r}) transient failure " \
           f"on attempt {attempt}/{max_attempts}"


def with_retry(
    fn: Callable[[], Any],
    *,
    provider: str,
    model: str,
    max_attempts: int = MAX_ATTEMPTS,
) -> Any:
    """Execute ``fn`` with bounded exponential-backoff retry.

    ``fn`` should raise ``httpx`` exceptions (HTTPStatusError/Timeouts/
    network errors). Classification decides what is retried:
    - transient errors are retried up to ``max_attempts`` (default 3)
    - permanent errors raise ``ProviderConfigError`` immediately
    - exhaustion raises ``ProviderUnavailableError``
    - anything unclassifiable propagates unchanged

    Runs synchronously (provider calls are synchronous and execute inside
    worker threads); cancellation is preserved because a cancelled
    thread's fn call is never re-invoked after the loop exits.
    """
    attempts = 0
    last_cause = "no response"
    while True:
        attempts += 1
        try:
            return fn()
        except ProviderConfigError:
            raise
        except Exception as exc:  # noqa: BLE001 - classification below
            verdict = classify_exception(exc)
            if verdict is None:
                raise
            if verdict == "permanent":
                raise ProviderConfigError(provider, str(exc)) from exc
            last_cause = str(exc)
            if attempts >= max_attempts:
                logger.warning(
                    f"{_fmt_attempt(provider, model, attempts, max_attempts)} — "
                    f"retries exhausted: {last_cause}"
                )
                raise ProviderUnavailableError(provider, model, last_cause) from exc
            delay = _backoff_delay(attempts, retry_after_seconds(exc))
            logger.warning(
                f"{_fmt_attempt(provider, model, attempts, max_attempts)} — retrying "
                f"in {delay:.1f}s: {last_cause}"
            )
            time.sleep(delay)