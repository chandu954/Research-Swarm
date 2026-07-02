"""Slack plugin — search messages, list channels."""
from __future__ import annotations
import os
from typing import Dict, Any, List, Optional
from loguru import logger
import httpx

from backend.plugins.base import Plugin, PluginSpec


SLACK_API = "https://slack.com/api"


class SlackPlugin(Plugin):
    def spec(self) -> PluginSpec:
        return PluginSpec(
            name="slack",
            description="Slack integration — search messages, list channels",
            version="1.0.0",
            config_schema={"token": "string"},
            actions=["search_messages", "list_channels", "get_channel_history"],
        )

    def _on_initialize(self) -> None:
        token = self.config.get("token") or os.getenv("SLACK_TOKEN")
        self._client = httpx.Client(
            base_url=SLACK_API,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )

    def execute(self, action: str, **kwargs: Any) -> Any:
        self.initialize()
        fn = getattr(self, f"_{action}", None)
        if not fn:
            raise ValueError(f"Unknown Slack action: {action}")
        return fn(**kwargs)

    def _search_messages(self, query: str, count: int = 10) -> List[Dict]:
        resp = self._client.get("/search.messages", params={"query": query, "count": count})
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")
        matches = data.get("messages", {}).get("matches", [])
        return [
            {
                "text": m.get("text", ""),
                "channel": m.get("channel", {}).get("name", ""),
                "user": m.get("username", ""),
                "ts": m.get("ts", ""),
                "permalink": m.get("permalink", ""),
            }
            for m in matches
        ]

    def _list_channels(self, limit: int = 100) -> List[Dict]:
        resp = self._client.get("/conversations.list", params={"limit": limit, "types": "public_channel"})
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")
        return [
            {
                "id": ch["id"],
                "name": ch["name"],
                "topic": ch.get("topic", {}).get("value", ""),
                "member_count": ch.get("member_count", 0),
            }
            for ch in data.get("channels", [])
        ]

    def _get_channel_history(self, channel: str, limit: int = 10) -> List[Dict]:
        resp = self._client.get("/conversations.history", params={"channel": channel, "limit": limit})
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")
        return [
            {
                "text": m.get("text", ""),
                "user": m.get("user", ""),
                "ts": m.get("ts", ""),
            }
            for m in data.get("messages", [])
        ]
