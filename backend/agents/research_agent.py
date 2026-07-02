"""Web research agent with DuckDuckGo search and page content extraction."""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from loguru import logger

from backend.tools.registry import ToolRegistry, get_registry, ToolSpec, ToolCategory


class WebResearchAgent:
    """Agent for searching the web and extracting page content."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        max_results: int = 5,
    ):
        self.registry = registry or get_registry()
        self.max_results = max_results
        self._register_tools()
        logger.info(f"WebResearchAgent ready (max_results={max_results})")

    def _register_tools(self) -> None:
        """Register available tools if not already registered."""
        try:
            self.registry.get_spec("web_search")
        except KeyError:
            from backend.tools.search import search_web as search_fn
            self.registry.register(
                "web_search",
                search_fn,
                ToolSpec(
                    name="web_search",
                    description="Search the web using DuckDuckGo",
                    category=ToolCategory.SEARCH,
                    input_schema={"query": "string", "max_results": "int"},
                ),
            )

    def run(self, query: str) -> List[Dict[str, Any]]:
        """Execute web research: search, extract, and return structured results."""
        logger.info(f"Researching: {query[:100]}...")

        try:
            raw_results = self.registry.execute(
                "web_search",
                query=query,
                max_results=self.max_results,
            )
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []

        results = []
        for item in raw_results:
            result = {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "source": item.get("source", "duckduckgo"),
            }
            results.append(result)
            logger.debug(f"Result: {result['title'][:80]}... | {result['url']}")

        return results
