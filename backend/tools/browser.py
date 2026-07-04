"""Web page reader — fetches and extracts readable content from URLs."""
from __future__ import annotations
from typing import Any
from loguru import logger

try:
    import httpx
except ImportError:
    httpx = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_TIMEOUT = 15.0
_MAX_TEXT_LENGTH = 100_000


def read_page(
    url: str,
    max_length: int = _MAX_TEXT_LENGTH,
) -> dict[str, Any]:
    """Fetch a URL and extract readable content.

    Args:
        url: The web page URL to read.
        max_length: Maximum characters of extracted text.

    Returns:
        Dict with keys: url, title, text, snippet, success, error.
    """
    if httpx is None:
        return {"url": url, "success": False, "error": "httpx not installed"}

    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return {"url": url, "success": False, "error": str(e)}

    return _extract_content(url, html, max_length)


def _extract_content(url: str, html: str, max_length: int) -> dict[str, Any]:
    """Parse HTML and extract readable text content."""
    if BeautifulSoup is None:
        return {
            "url": url,
            "title": "",
            "text": html[:max_length],
            "snippet": html[:200].strip(),
            "success": True,
        }

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    for selector in ["article", "main", "[role=main]", ".content", "#content", "body"]:
        container = soup.select_one(selector)
        if container:
            break
    else:
        container = soup.body or soup

    text = container.get_text(separator="\n", strip=True)
    text = text[:max_length]

    snippet = text[:200].strip()

    return {
        "url": url,
        "title": title,
        "text": text,
        "snippet": snippet,
        "success": True,
    }


def extract_links(url: str, max_links: int = 20) -> list[dict[str, str]]:
    """Extract all links from a page."""
    if httpx is None or BeautifulSoup is None:
        return []

    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True)[:max_links]:
            href = a["href"]
            text = a.get_text(strip=True)[:100]
            if href.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            links.append({"url": href, "text": text})
        return links
    except Exception as e:
        logger.warning(f"Failed to extract links from {url}: {e}")
        return []
