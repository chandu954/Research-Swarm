from __future__ import annotations
from typing import Any


def merge_research(
    web_results: list[dict[str, Any]],
    document_chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    merged_evidence: list[dict[str, Any]] = []
    seen_contents: set[str] = set()

    for r in web_results:
        text = r.get("content", "") or r.get("snippet", "") or r.get("title", "")
        if not text or text.strip() in seen_contents:
            continue
        seen_contents.add(text.strip())
        merged_evidence.append({
            "type": "web",
            "title": r.get("title", ""),
            "content": text,
            "url": r.get("url", ""),
            "source": r.get("source", "web"),
        })

    for c in document_chunks:
        text = c.get("content", "") or c.get("text", "")
        if not text or text.strip() in seen_contents:
            continue
        seen_contents.add(text.strip())
        merged_evidence.append({
            "type": "document",
            "title": c.get("filename", c.get("title", "Document")),
            "content": text,
            "url": "",
            "source": "document",
            "page": c.get("page"),
        })

    has_evidence = len(merged_evidence) > 0
    return {
        "merged_evidence": merged_evidence,
        "has_evidence": has_evidence,
        "source_count": len(web_results),
        "document_count": len(document_chunks),
    }
