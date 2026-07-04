# Plugin Development Guide

ResearchSwarm uses a unified plugin architecture based on `PluginInterface` (defined in `backend/core/plugin.py`). All major systems — LLMs, search, embeddings, vector stores, storage, memory, and external integrations — are plugins.

## Architecture

```
PluginInterface (ABC)
  ├── LLMProvider        (core/providers/llm.py)
  ├── SearchProvider     (core/providers/search.py)
  ├── EmbeddingProvider  (core/providers/embedding.py)
  ├── VectorDBProvider   (core/providers/vector_db.py)
  ├── StorageProvider    (core/providers/storage.py)
  ├── MemoryProvider     (core/providers/memory.py)
  └── Plugin             (plugins/base.py, for external APIs)
```

All plugins share a common lifecycle via `PluginInterface`:

```python
class PluginInterface(ABC):
    spec: PluginSpec                    # name, version, description, config schema

    @abstractmethod
    async def initialize(self) -> None  # called once at startup

    @abstractmethod
    async def cleanup(self) -> None     # called once at shutdown
```

## Creating a New Plugin

### 1. Define your plugin class

Implement `PluginInterface` plus the provider-specific interface you need:

```python
from backend.core.plugin import PluginInterface, PluginSpec
from backend.core.providers.search import SearchProvider

class CustomSearchProvider(SearchProvider):
    @property
    def spec(self) -> PluginSpec:
        return PluginSpec(
            name="custom_search",
            version="1.0.0",
            description="Custom search engine",
            config_schema={
                "api_key": {"type": "string", "description": "API key"},
            },
        )

    async def initialize(self) -> None:
        api_key = self.spec.config.get("api_key")
        self._client = httpx.AsyncClient(headers={"Authorization": f"Bearer {api_key}"})

    async def cleanup(self) -> None:
        await self._client.aclose()

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        resp = await self._client.get("https://api.example.com/search", params={"q": query, "n": max_results})
        resp.raise_for_status()
        return resp.json()["results"]
```

### 2. Register with the PluginRegistry

In `backend/api/main.py` in `_register_builtin_plugins()`:

```python
try:
    custom = CustomSearchProvider(config={"api_key": os.getenv("CUSTOM_SEARCH_KEY", "")})
    await custom.initialize()
    registry.register(custom, "search")
    logger.info("Registered custom search provider")
except Exception as e:
    logger.warning(f"Failed to register custom search: {e}")
```

Or register at runtime via the `/plugins/{name}/configure` endpoint.

### 3. Plugin resolution order

- `registry.get_search()` — returns the **default** search provider (first registered with `default=True`)
- `registry.get_search("custom_search")` — returns a specific provider by name
- `registry.list_plugins("search")` — all registered search providers

The parallel aggregator (`backend/search/aggregator.py`) queries **all** search providers concurrently and deduplicates results.

## External (API) Plugins

For third-party integrations (GitHub, Notion, Slack, etc.), extend `Plugin`:

```python
from backend.plugins.base import Plugin

class MyServicePlugin(Plugin):
    @property
    def spec(self) -> PluginSpec:
        return PluginSpec(
            name="myservice",
            version="1.0.0",
            description="My external service",
        )

    async def initialize(self) -> None:
        self._token = self.spec.config.get("token")

    async def execute(self, action: str, params: dict) -> dict:
        if action == "list_items":
            return await self._fetch_items(params.get("limit", 10))
        raise ValueError(f"Unknown action: {action}")

    async def _fetch_items(self, limit: int) -> dict:
        # Call external API
        return {"items": []}
```

## Tests

Create tests under `backend/tests/`. Use the test fixtures in `test_core_registry.py` as a reference:

```python
async def test_custom_provider():
    registry = get_plugin_registry()
    reset_plugin_registry()
    provider = CustomSearchProvider(config={"api_key": "test"})
    await provider.initialize()
    registry.register(provider, "search", default=True)
    assert registry.is_configured("search")
    await provider.cleanup()
```

## Configuration

Plugins receive configuration via their `spec.config` dict, populated from:
1. The `config` argument passed at construction time
2. The `/plugins/{name}/configure` API endpoint (persisted to DB for the `Provider` model)

Environment variables for sensitive values (API keys, tokens) are set in the backend's `.env` file and passed during `_register_builtin_plugins()`.
