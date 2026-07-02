"""Notion plugin — query databases, read pages."""
from __future__ import annotations
import os
from typing import Dict, Any, List, Optional
from loguru import logger
import httpx

from backend.plugins.base import Plugin, PluginSpec


NOTION_API = "https://api.notion.com/v1"


class NotionPlugin(Plugin):
    def spec(self) -> PluginSpec:
        return PluginSpec(
            name="notion",
            description="Notion integration — query databases, read pages",
            version="1.0.0",
            config_schema={"token": "string"},
            actions=["query_database", "get_page", "search"],
        )

    def _on_initialize(self) -> None:
        token = self.config.get("token") or os.getenv("NOTION_TOKEN")
        self._client = httpx.Client(
            base_url=NOTION_API,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )

    def execute(self, action: str, **kwargs: Any) -> Any:
        self.initialize()
        fn = getattr(self, f"_{action}", None)
        if not fn:
            raise ValueError(f"Unknown Notion action: {action}")
        return fn(**kwargs)

    def _query_database(self, database_id: str, filter_: Optional[Dict] = None) -> List[Dict]:
        body: Dict[str, Any] = {}
        if filter_:
            body["filter"] = filter_
        resp = self._client.post(f"/databases/{database_id}/query", json=body)
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "id": page["id"],
                "url": page.get("url", ""),
                "properties": {
                    k: _notion_prop_value(v) for k, v in page.get("properties", {}).items()
                },
                "created_time": page["created_time"],
            }
            for page in data.get("results", [])
        ]

    def _get_page(self, page_id: str) -> Dict:
        resp = self._client.get(f"/pages/{page_id}")
        resp.raise_for_status()
        page = resp.json()
        return {
            "id": page["id"],
            "url": page.get("url", ""),
            "properties": {
                k: _notion_prop_value(v) for k, v in page.get("properties", {}).items()
            },
        }

    def _search(self, query: str) -> List[Dict]:
        resp = self._client.post("/search", json={"query": query})
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "id": r["id"],
                "type": r.get("object"),
                "url": r.get("url", ""),
            }
            for r in data.get("results", [])
        ]


def _notion_prop_value(prop: Dict) -> Any:
    ptype = prop.get("type")
    if not ptype:
        return None
    val = prop.get(ptype)
    if isinstance(val, dict):
        return val.get("content") or val.get("name") or val.get("plain_text") or str(val)
    if isinstance(val, list):
        return " ".join(v.get("plain_text", "") for v in val)
    return val
