"""Web search tool with multiple backend support (DuckDuckGo, Bing, Serper)."""
import os, re, json, time, urllib.parse
from typing import List, Dict, Any, Optional
from loguru import logger
from pydantic import BaseModel, Field
import httpx


class WebSearchResult(BaseModel):
    title: str = Field(..., description="Result title")
    url: str = Field(..., description="Result URL")
    snippet: str = Field(..., description="Result snippet")
    source: str = Field(default="duckduckgo", description="Search source")


BACKENDS = ["html", "auto", "lite"]
_HTTP_TIMEOUT = 20.0


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
    ddgs_module = None
    for mod_name in ["ddgs", "duckduckgo_search"]:
        try:
            ddgs_module = __import__(mod_name, fromlist=["DDGS"])
            break
        except ImportError:
            continue

    if ddgs_module is None:
        logger.error("No DuckDuckGo search package installed (tried ddgs, duckduckgo_search)")
        return _search_fallback(query, max_results)

    DDGS = ddgs_module.DDGS
    logger.info(f"[DuckDuckGo] Searching: {query[:100]}...")
    last_error = None
    for attempt in range(2):
        for backend in BACKENDS:
            try:
                with DDGS() as ddgs:
                    raw = list(ddgs.text(query, region=region, safesearch=safesearch, max_results=max_results * 2, backend=backend))
                if raw:
                    logger.info(f"[DuckDuckGo] Backend '{backend}' returned {len(raw)} results (attempt {attempt+1})")
                    return _format_results(raw, "duckduckgo")
                logger.debug(f"[DuckDuckGo] Backend '{backend}' returned 0 results (attempt {attempt+1})")
            except Exception as e:
                last_error = e
                logger.debug(f"[DuckDuckGo] Backend '{backend}' failed (attempt {attempt+1}): {e}")
        if attempt == 0:
            time.sleep(1.0)

    logger.warning(f"[DuckDuckGo] All backends failed after retry, trying fallback search. Last error: {last_error}")
    return _search_fallback(query, max_results)


def _search_bing(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    api_key = os.getenv("BING_API_KEY")
    if not api_key:
        logger.warning("BING_API_KEY not set, falling back to DuckDuckGo")
        return _search_duckduckgo(query, max_results)

    logger.info(f"[Bing] Searching: {query[:100]}...")
    endpoint = "https://api.bing.microsoft.com/v7.0/search"
    params = {"q": query, "count": max_results, "mkt": "en-US"}
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.get(endpoint, params=params, headers={"Ocp-Apim-Subscription-Key": api_key})
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


def _search_serper(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        logger.warning("SERPER_API_KEY not set, falling back to DuckDuckGo")
        return _search_duckduckgo(query, max_results)

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


def _search_fallback(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Last-resort fallback using direct DuckDuckGo Lite HTML scraping."""
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


def hybrid_search_web(
    query: str,
    max_results: int = 5,
    region: str = "wt-wt",
    safesearch: str = "moderate",
) -> List[Dict[str, Any]]:
    """Search the web and hybrid-rerank results by BM25 + embedding relevance."""
    raw = search_web(query, max_results * 2, region, safesearch)
    if not raw:
        return []

    from backend.search.hybrid import hybrid_rerank
    from backend.llm.factory import get_llm_provider_instance

    try:
        llm = get_llm_provider_instance()
        embed_fn = lambda t: llm.create_embedding(text=t, model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text"))
        reranked = hybrid_rerank(query, raw, bm25_weight=0.3, top_k=max_results, embed_fn=embed_fn)
        return reranked
    except Exception as e:
        logger.warning(f"Hybrid rerank failed, falling back to raw results: {e}")
        return raw[:max_results]


def _clean_url(url: str) -> str:
    if not url:
        return ""
    url = re.sub(r"[\?&](utm_|ref|source|camp|medium|content|mc)=[^&]*", "", url)
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url
