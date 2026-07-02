"""Web search tool with multiple backend support (DuckDuckGo, Bing, Serper)."""
import os, re, json, time, urllib.request, urllib.parse
from typing import List, Dict, Any, Optional
from loguru import logger
from pydantic import BaseModel, Field


class WebSearchResult(BaseModel):
    title: str = Field(..., description="Result title")
    url: str = Field(..., description="Result URL")
    snippet: str = Field(..., description="Result snippet")
    source: str = Field(default="duckduckgo", description="Search source")


BACKENDS = ["html", "auto", "lite"]


def search_web(
    query: str,
    max_results: int = 5,
    region: str = "wt-wt",
    safesearch: str = "moderate",
) -> List[Dict[str, Any]]:
    """Search the web using DuckDuckGo or a configured API backend."""
    backend = os.getenv("SEARCH_BACKEND", "duckduckgo").lower()
    if backend == "bing":
        return _search_bing(query, max_results)
    elif backend == "serper":
        return _search_serper(query, max_results)
    return _search_duckduckgo(query, max_results, region, safesearch)


def _search_duckduckgo(
    query: str, max_results: int = 5, region: str = "wt-wt", safesearch: str = "moderate"
) -> List[Dict[str, Any]]:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("duckduckgo-search package not installed")
        return _search_fallback(query, max_results)

    logger.info(f"[DuckDuckGo] Searching: {query[:100]}...")
    for backend in BACKENDS:
        try:
            with DDGS() as ddgs:
                raw = list(ddgs.text(keywords=query, region=region, safesearch=safesearch, max_results=max_results, backend=backend))
            if raw:
                logger.info(f"[DuckDuckGo] Backend '{backend}' returned {len(raw)} results")
                return _format_results(raw, "duckduckgo")
            logger.debug(f"[DuckDuckGo] Backend '{backend}' returned 0 results")
        except Exception as e:
            logger.debug(f"[DuckDuckGo] Backend '{backend}' failed: {e}")

    logger.warning("[DuckDuckGo] All backends failed, trying fallback search")
    return _search_fallback(query, max_results)


def _search_bing(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    api_key = os.getenv("BING_API_KEY")
    if not api_key:
        logger.warning("BING_API_KEY not set, falling back to DuckDuckGo")
        return _search_duckduckgo(query, max_results)

    logger.info(f"[Bing] Searching: {query[:100]}...")
    endpoint = "https://api.bing.microsoft.com/v7.0/search"
    params = urllib.parse.urlencode({"q": query, "count": max_results, "mkt": "en-US"})
    try:
        req = urllib.request.Request(f"{endpoint}?{params}", headers={"Ocp-Apim-Subscription-Key": api_key})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
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


def _search_serper(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        logger.warning("SERPER_API_KEY not set, falling back to DuckDuckGo")
        return _search_duckduckgo(query, max_results)

    logger.info(f"[Serper] Searching: {query[:100]}...")
    payload = json.dumps({"q": query, "num": max_results}).encode()
    try:
        req = urllib.request.Request(
            "https://google.serper.dev/search",
            data=payload,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
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


def _search_fallback(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Last-resort fallback using direct DuckDuckGo Lite HTML scraping."""
    logger.info(f"[Fallback] Searching: {query[:100]}...")
    url = "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(query)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode()

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

        logger.warning("[Fallback] No results found from DuckDuckGo Lite")
    except Exception as e:
        logger.error(f"[Fallback] Search failed: {e}")

    return []


def _format_results(raw: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
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
