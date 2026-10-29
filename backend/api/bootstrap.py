"""Application lifecycle and built-in plugin registration.

Kept separate from the FastAPI app factory so startup wiring can be tested
and evolved without growing the route module.
"""

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from backend.agents.graph import create_research_graph
from backend.agents.memory import get_memory
from backend.api.stream import get_stream_manager
from backend.core.logging import setup_logging
from backend.core.registry import get_plugin_registry, reset_plugin_registry
from backend.db.session import close_db, init_db
from backend.tools.registry import get_registry


async def register_builtin_plugins() -> None:
    """Register and initialize all built-in plugins."""
    registry = get_plugin_registry()
    reset_plugin_registry()
    registry = get_plugin_registry()

    # LLM providers
    from backend.llm.ollama_provider import OllamaProvider
    from backend.llm.openrouter_provider import OpenRouterProvider

    try:
        ollama = OllamaProvider()
        await ollama.initialize()
        registry.register(ollama, "llm")
        logger.info("Registered Ollama LLM provider")
    except Exception as e:
        logger.warning(f"Failed to register Ollama: {e}")

    try:
        openrouter = OpenRouterProvider()
        await openrouter.initialize()
        registry.register(openrouter, "llm", default=True)
        logger.info("Registered OpenRouter LLM provider")
    except Exception as e:
        logger.warning(f"Failed to register OpenRouter: {e}")

    # Search providers
    from backend.providers.search import (
        BingProvider,
        DuckDuckGoProvider,
        SerperProvider,
    )

    for name, cls, is_default in [
        ("duckduckgo", DuckDuckGoProvider, True),
        ("bing", BingProvider, False),
        ("serper", SerperProvider, False),
    ]:
        try:
            prov = cls()
            await prov.initialize()
            registry.register(prov, "search", default=is_default)
            logger.info(f"Registered search provider: {name}")
        except Exception as e:
            logger.warning(f"Failed to register search {name}: {e}")

    # Embedding providers
    from backend.providers.embedding import (
        OllamaEmbeddingProvider,
        OpenRouterEmbeddingProvider,
    )

    try:
        emb = OllamaEmbeddingProvider()
        await emb.initialize()
        registry.register(emb, "embedding", default=True)
        logger.info("Registered Ollama embedding provider")
    except Exception as e:
        logger.warning(f"Failed to register Ollama embedding: {e}")

    try:
        emb = OpenRouterEmbeddingProvider()
        await emb.initialize()
        registry.register(emb, "embedding")
        logger.info("Registered OpenRouter embedding provider")
    except Exception as e:
        logger.warning(f"Failed to register OpenRouter embedding: {e}")

    # External integration plugins
    from backend.plugins.github import GitHubPlugin
    from backend.plugins.notion import NotionPlugin
    from backend.plugins.slack import SlackPlugin
    from backend.plugins.weather import WeatherPlugin

    for p_cls, cfg_key, name in [
        (GitHubPlugin, "GITHUB_TOKEN", "github"),
        (NotionPlugin, "NOTION_TOKEN", "notion"),
        (SlackPlugin, "SLACK_TOKEN", "slack"),
        (WeatherPlugin, None, "weather"),
    ]:
        try:
            config = {"token": os.getenv(cfg_key, "")} if cfg_key else {}
            inst = p_cls(config=config)
            await inst.initialize()
            registry.register(inst, "external")
            logger.info(f"Registered external plugin: {name}")
        except Exception as e:
            logger.warning(f"Failed to register plugin {name}: {e}")

    # Vector DB provider
    from backend.providers.vector_db import ChromaDBVectorStore

    try:
        vdb = ChromaDBVectorStore()
        await vdb.initialize()
        registry.register(vdb, "vector_db", default=True)
        logger.info("Registered ChromaDB vector store provider")
    except Exception as e:
        logger.warning(f"Failed to register ChromaDB vector store: {e}")

    # Storage provider
    from backend.providers.storage import LocalStorageProvider

    try:
        storage = LocalStorageProvider()
        await storage.initialize()
        registry.register(storage, "storage", default=True)
        logger.info("Registered local storage provider")
    except Exception as e:
        logger.warning(f"Failed to register local storage: {e}")

    # Memory provider
    from backend.providers.memory import ConversationMemoryProvider

    try:
        mem = ConversationMemoryProvider()
        await mem.initialize()
        registry.register(mem, "memory", default=True)
        logger.info("Registered conversation memory provider")
    except Exception as e:
        logger.warning(f"Failed to register memory provider: {e}")

    logger.info(f"Plugin registration complete — {len(registry.list())} plugins total")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    from backend.core.config import validate_secrets

    validate_secrets()
    logger.info("ResearchSwarm AI starting up")
    app.state.start_time = time.time()
    await init_db()
    app.state.graph = create_research_graph()
    app.state.memory = get_memory()
    app.state.registry = get_registry()
    app.state.stream_manager = get_stream_manager()
    try:
        tools = app.state.registry.list_tools()
        logger.info(f"Tools registered: {[t.name for t in tools]}")
    except Exception as e:
        logger.warning(f"Tool listing failed: {e}")

    await register_builtin_plugins()
    app.state.plugin_registry = get_plugin_registry()

    yield
    # Cancel any still-running research streams before DB/plugin teardown.
    try:
        await app.state.stream_manager.cancel_all_tasks()
    except Exception as exc:  # pragma: no cover - resilience path
        logger.warning(f"Stream task cancellation on shutdown failed: {exc}")
    await close_db()
    # Cleanup all registered plugins
    registry = get_plugin_registry()
    for name in list(registry._plugins):
        plugin = registry._plugins[name]
        try:
            await plugin.cleanup()
            logger.debug(f"Cleaned up plugin: {name}")
        except Exception as e:
            logger.warning(f"Plugin cleanup failed for {name}: {e}")
    logger.info("ResearchSwarm AI shutting down")
