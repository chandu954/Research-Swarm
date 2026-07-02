"""GitHub plugin — search issues, PRs, repos."""
from __future__ import annotations
import os
from typing import Dict, Any, List, Optional
from loguru import logger
import httpx

from backend.plugins.base import Plugin, PluginSpec


GITHUB_API = "https://api.github.com"


class GitHubPlugin(Plugin):
    def spec(self) -> PluginSpec:
        return PluginSpec(
            name="github",
            description="GitHub integration — search issues, PRs, repos, read files",
            version="1.0.0",
            config_schema={
                "token": "string",
            },
            actions=[
                "search_issues",
                "search_repos",
                "get_repo",
                "list_issues",
                "get_file",
            ],
        )

    def _on_initialize(self) -> None:
        token = self.config.get("token") or os.getenv("GITHUB_TOKEN")
        if token:
            self._client = httpx.Client(
                base_url=GITHUB_API,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "ResearchSwarm/1.0",
                },
                timeout=15.0,
            )
        else:
            self._client = httpx.Client(
                base_url=GITHUB_API,
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "ResearchSwarm/1.0"},
                timeout=15.0,
            )

    def execute(self, action: str, **kwargs: Any) -> Any:
        self.initialize()
        fn = getattr(self, f"_{action}", None)
        if not fn:
            raise ValueError(f"Unknown GitHub action: {action}")
        return fn(**kwargs)

    def _search_issues(self, query: str, per_page: int = 10) -> List[Dict]:
        resp = self._client.get("/search/issues", params={"q": query, "per_page": per_page})
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": item["title"],
                "url": item["html_url"],
                "state": item["state"],
                "repo": item["repository_url"].split("/")[-1],
                "created_at": item["created_at"],
                "body": item["body"][:500] if item.get("body") else "",
            }
            for item in data.get("items", [])
        ]

    def _search_repos(self, query: str, per_page: int = 10) -> List[Dict]:
        resp = self._client.get("/search/repositories", params={"q": query, "per_page": per_page})
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "name": item["full_name"],
                "url": item["html_url"],
                "description": item["description"],
                "stars": item["stargazers_count"],
                "language": item["language"],
                "topics": item.get("topics", []),
            }
            for item in data.get("items", [])
        ]

    def _get_repo(self, repo: str) -> Dict:
        resp = self._client.get(f"/repos/{repo}")
        resp.raise_for_status()
        d = resp.json()
        return {
            "name": d["full_name"],
            "description": d["description"],
            "stars": d["stargazers_count"],
            "forks": d["forks_count"],
            "language": d["language"],
            "topics": d.get("topics", []),
            "url": d["html_url"],
        }

    def _list_issues(self, repo: str, state: str = "open", per_page: int = 10) -> List[Dict]:
        resp = self._client.get(
            f"/repos/{repo}/issues",
            params={"state": state, "per_page": per_page, "sort": "updated"},
        )
        resp.raise_for_status()
        return [
            {
                "title": item["title"],
                "url": item["html_url"],
                "state": item["state"],
                "created_at": item["created_at"],
                "labels": [l["name"] for l in item.get("labels", [])],
            }
            for item in resp.json()
        ]

    def _get_file(self, repo: str, path: str, ref: str = "main") -> str:
        resp = self._client.get(f"/repos/{repo}/contents/{path}", params={"ref": ref})
        resp.raise_for_status()
        import base64
        content = resp.json().get("content", "")
        return base64.b64decode(content).decode("utf-8") if content else ""
