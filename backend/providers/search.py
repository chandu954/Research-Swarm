"""Built-in search providers: DuckDuckGo, Bing, Serper, fallback."""
from __future__ import annotations
import os, re, time, urllib.parse
from typing import Any
from loguru import logger
import httpx

from backend.providers.base import SearchProvider, ProviderInfo


_BACKENDS = ["html", "auto", "lite"]
_HTTP_TIMEOUT = 20.0


class DuckDuckGoProvider(SearchProvider):
    def search(self, query: str, max_results: int = 5, **kwargs: Any) -> list[dict[str, Any]]:
        region = kwargs.get("region", "wt-wt")
        safesearch = kwargs.get("safesearch", "moderate")
        return self._search(query, max_results, region, safesearch)

    def _search(self, query: str, max_results: int, region: str, safesearch: str) -> list[dict[str, Any]]:
        ddgs_module = None
        for mod_name in ["ddgs", "duckduckgo_search"]:
            try:
                ddgs_module = __import__(mod_name, fromlist=["DDGS"])
                break
            except ImportError:
                continue

        if ddgs_module is None:
            logger.error("No DuckDuckGo search package installed (tried ddgs, duckduckgo_search)")
            return _fallback_search(query, max_results)

        DDGS = ddgs_module.DDGS
        logger.info(f"[DuckDuckGo] Searching: {query[:100]}...")
        last_error = None
        for attempt in range(2):
            for backend in _BACKENDS:
                try:
                    with DDGS() as ddgs:
                        raw = list(ddgs.text(query, region=region, safesearch=safesearch, max_results=max_results * 2, backend=backend))
                    if raw:
                        logger.info(f"[DuckDuckGo] Backend '{backend}' returned {len(raw)} results (attempt {attempt+1})")
                        return _format_results(raw, "duckduckgo")
                except Exception as e:
                    last_error = e
            if attempt == 0:
                time.sleep(1.0)

        logger.warning(f"[DuckDuckGo] All backends failed, trying fallback. Last error: {last_error}")
        return _fallback_search(query, max_results)

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(name="duckduckgo", description="DuckDuckGo search (no API key needed)")


class BingProvider(SearchProvider):
    def search(self, query: str, max_results: int = 5, **kwargs: Any) -> list[dict[str, Any]]:
        api_key = os.getenv("BING_API_KEY")
        if not api_key:
            logger.warning("BING_API_KEY not set, falling back to DuckDuckGo")
            return DuckDuckGoProvider().search(query, max_results, **kwargs)

        logger.info(f"[Bing] Searching: {query[:100]}...")
        try:
            with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
                resp = client.get(
                    "https://api.bing.microsoft.com/v7.0/search",
                    params={"q": query, "count": max_results, "mkt": "en-US"},
                    headers={"Ocp-Apim-Subscription-Key": api_key},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error(f"[Bing] Search failed: {e}")
            return []

        results = []
        for i, item in enumerate(data.get("webPages", {}).get("value", [])[:max_results]):
            results.append({
                "title": item.get("name", f"Result {i+1}"),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "source": "bing",
                "position": i + 1,
            })
        logger.info(f"[Bing] Found {len(results)} results")
        return results

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="bing",
            description="Microsoft Bing Search API",
            config_schema={"api_key": {"type": "string", "env_var": "BING_API_KEY"}},
        )


class SerperProvider(SearchProvider):
    def search(self, query: str, max_results: int = 5, **kwargs: Any) -> list[dict[str, Any]]:
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            logger.warning("SERPER_API_KEY not set, falling back to DuckDuckGo")
            return DuckDuckGoProvider().search(query, max_results, **kwargs)

        logger.info(f"[Serper] Searching: {query[:100]}...")
        try:
            with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
                resp = client.post(
                    "https://google.serper.dev/search",
                    json={"q": query, "num": max_results},
                    headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error(f"[Serper] Search failed: {e}")
            return []

        results = []
        for i, item in enumerate(data.get("organic", [])[:max_results]):
            results.append({
                "title": item.get("title", f"Result {i+1}"),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "serper",
                "position": i + 1,
            })
        logger.info(f"[Serper] Found {len(results)} results")
        return results

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="serper",
            description="Serper.dev Google Search API",
            config_schema={"api_key": {"type": "string", "env_var": "SERPER_API_KEY"}},
        )


def _fallback_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    logger.info(f"[Fallback] Searching: {query[:100]}...")
    url = "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(query)
    try:
        with httpx.Client(verify=False, timeout=_HTTP_TIMEOUT) as client:
            resp = client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            })
            resp.raise_for_status()
            html = resp.text

        results = []
        for m in re.finditer(
            r'<a[^>]*href="(https?://[^"]+)"[^>]*class="result-link"[^>]*>(.*?)</a>',
            html, re.DOTALL
        ):
            results.append({
                "title": re.sub(r"<[^>]+>", "", m.group(2)).strip(),
                "url": m.group(1),
                "snippet": "",
                "source": "fallback",
                "position": len(results) + 1,
            })

        if results:
            logger.info(f"[Fallback] Found {len(results)} results")
            return results[:max_results]

        logger.warning("[Fallback] No results from DuckDuckGo Lite")
    except Exception as e:
        logger.error(f"[Fallback] Search failed: {e}")

    return []


def _format_results(raw: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    results = []
    for i, item in enumerate(raw):
        url = _clean_url(item.get("href", ""))
        if not url:
            continue
        results.append({
            "title": item.get("title", f"Result {i+1}"),
            "url": url,
            "snippet": item.get("body", ""),
            "source": source,
            "position": i + 1,
        })
    return results


def _clean_url(url: str) -> str:
    if not url:
        return ""
    url = re.sub(r"[\?&](utm_|ref|source|camp|medium|content|mc)=[^&]*", "", url)
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url
