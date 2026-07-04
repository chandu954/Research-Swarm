"""Web research agent with search, page reading, and code execution."""
from __future__ import annotations
from typing import Any
from loguru import logger

from backend.tools.registry import ToolRegistry, get_registry, ToolSpec, ToolCategory


class WebResearchAgent:
    """Agent for searching the web, reading pages, and executing code."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        max_results: int = 5,
    ):
        self.registry = registry or get_registry()
        self.max_results = max_results
        self._register_tools()
        logger.info(f"WebResearchAgent ready (max_results={max_results})")

    def _register_tools(self) -> None:
        try:
            self.registry.get_spec("web_search")
        except KeyError:
            from backend.tools.search import hybrid_search_web as search_fn
            self.registry.register(
                "web_search",
                search_fn,
                ToolSpec(
                    name="web_search",
                    description="Search the web with hybrid BM25+dense reranking",
                    category=ToolCategory.SEARCH,
                    input_schema={"query": "string", "max_results": "int"},
                ),
            )

        try:
            self.registry.get_spec("read_page")
        except KeyError:
            from backend.tools.browser import read_page as read_fn
            self.registry.register(
                "read_page",
                read_fn,
                ToolSpec(
                    name="read_page",
                    description="Fetch a URL and extract readable content",
                    category=ToolCategory.BROWSER,
                    input_schema={"url": "string", "max_length": "int"},
                ),
            )

        try:
            self.registry.get_spec("extract_links")
        except KeyError:
            from backend.tools.browser import extract_links as links_fn
            self.registry.register(
                "extract_links",
                links_fn,
                ToolSpec(
                    name="extract_links",
                    description="Extract all links from a web page",
                    category=ToolCategory.BROWSER,
                    input_schema={"url": "string", "max_links": "int"},
                ),
            )

        try:
            self.registry.get_spec("execute_python")
        except KeyError:
            from backend.tools.code_executor import execute_python as py_fn
            self.registry.register(
                "execute_python",
                py_fn,
                ToolSpec(
                    name="execute_python",
                    description="Execute Python code in a sandboxed subprocess",
                    category=ToolCategory.CODE,
                    input_schema={"code": "string", "timeout": "int"},
                ),
            )

        try:
            self.registry.get_spec("execute_shell")
        except KeyError:
            from backend.tools.code_executor import execute_shell as sh_fn
            self.registry.register(
                "execute_shell",
                sh_fn,
                ToolSpec(
                    name="execute_shell",
                    description="Execute a shell command in a subprocess",
                    category=ToolCategory.CODE,
                    input_schema={"command": "string", "timeout": "int"},
                ),
            )

    def run(self, query: str) -> list[dict[str, Any]]:
        """Execute web research: search and return structured results."""
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

        return results
