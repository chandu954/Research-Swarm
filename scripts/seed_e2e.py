#!/usr/bin/env python
"""Idempotent E2E seed: one realistic demo workspace for the E2E test account.

Creates (per run, after removing any previous seed-tagged copies):
  - 1 completed research session + run metrics + 5 agent runs + chat messages
  - 3 'ready' reports (content + markdown file in Supabase storage)
  - 2 uploaded PDFs (real objects in the rs_documents bucket)
  - 1 collection with items linking reports and documents
  - 5 recent searches, 1 saved prompt, activity log entries

Safe by default: only touches E2E_TEST_EMAIL's account on a local instance.

Usage:
    .venv/bin/python scripts/seed_e2e.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

from e2e_common import assert_safe_target, load_env, list_recursive, psql, resolve_profile_id, test_email  # noqa: E402

load_env()
assert_safe_target()

from backend.core.supabase import get_supabase  # noqa: E402

UID = resolve_profile_id(test_email())
if not UID:
    print("No rs_profiles row for the E2E test account — cannot seed.")
    sys.exit(2)

sb = get_supabase()
NOW = datetime.now(timezone.utc)
MINI_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \ntrailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n0\n%%EOF\n"
)

SEED_COLLECTION = "E2E Demo Workspace"
SEED_SESSION_TITLE = "E2E Demo Research"
SEED_DOCS = ["e2e-demo-alpha.pdf", "e2e-demo-beta.pdf"]
SEED_REPORT_TITLES = [
    "E2E Demo Report: RAG vs Fine-tuning",
    "E2E Demo Report: Agent Evaluation Frameworks",
    "E2E Demo Report: RAG System Design",
]
SEED_SEARCHES = [
    "retrieval augmented generation overview",
    "LangGraph multi-agent workflows",
    "RAG evaluation frameworks 2026",
    "hybrid search embeddings vs BM25",
    "agent memory architectures",
]
SEED_PROMPT_LABEL = "E2E Demo: Summarize findings"


def wipe_seed_markers() -> tuple[int, int]:
    """Remove any previously seeded copies so re-runs stay idempotent."""
    docs_removed = 0
    for bucket in ["rs_documents", "rs_reports"]:
        paths = [p for p in list_recursive(bucket, f"{UID}/") if "e2e-demo-" in p]
        for i in range(0, len(paths), 1000):
            sb.storage.from_(bucket).remove(paths[i : i + 1000])
        docs_removed += len(paths)

    seed_sessions = [r["id"] for r in sb.table("rs_research_sessions")
                     .select("id").eq("user_id", UID).eq("title", SEED_SESSION_TITLE).execute().data]
    seed_collections = [r["id"] for r in sb.table("rs_collections")
                        .select("id").eq("user_id", UID).eq("name", SEED_COLLECTION).execute().data]
    seed_doc_ids = [r["id"] for r in sb.table("rs_documents")
                    .select("id").eq("user_id", UID).in_("name", SEED_DOCS).execute().data]

    rows_deleted = 0
    if seed_collections:
        rows_deleted += len(sb.table("rs_collection_items").delete().in_("collection_id", seed_collections).execute().data)
        rows_deleted += len(sb.table("rs_collections").delete().in_("id", seed_collections).execute().data)
    if seed_sessions:
        rows_deleted += len(sb.table("rs_messages").delete().in_("session_id", seed_sessions).execute().data)
        rows_deleted += len(sb.table("rs_agent_runs").delete().in_("session_id", seed_sessions).execute().data)
        rows_deleted += len(sb.table("rs_run_metrics").delete().in_("session_id", seed_sessions).execute().data)
        rows_deleted += len(sb.table("rs_research_sessions").delete().in_("id", seed_sessions).execute().data)
    if seed_doc_ids:
        rows_deleted += len(sb.table("rs_documents").delete().in_("id", seed_doc_ids).execute().data)
    for title in SEED_REPORT_TITLES:
        rows_deleted += len(sb.table("rs_reports").delete().eq("user_id", UID).eq("title", title).execute().data)
    for q in SEED_SEARCHES:
        rows_deleted += len(sb.table("rs_recent_searches").delete().eq("user_id", UID).eq("query", q).execute().data)
    rows_deleted += len(sb.table("rs_saved_prompts").delete().eq("user_id", UID).eq("label", SEED_PROMPT_LABEL).execute().data)
    rows_deleted += len(sb.table("rs_activity_logs").delete().eq("user_id", UID).contains("metadata", {"seed": "e2e"}).execute().data)
    return rows_deleted, docs_removed


def insert_session() -> str:
    sid = str(uuid4())
    now = NOW.isoformat()
    sb.table("rs_research_sessions").insert({
        "id": sid, "user_id": UID, "title": SEED_SESSION_TITLE,
        "prompt": "Compare RAG with fine-tuning for domain-specific question answering.",
        "mode": "quick", "debate_enabled": False, "status": "completed",
        "sources_total": 12, "created_at": now, "updated_at": now,
    }).execute()
    return sid


def insert_metrics(sid: str) -> None:
    sb.table("rs_run_metrics").insert({
        "session_id": sid, "execution_time_ms": 48321, "sources_found": 12,
        "relevant_sources": 9, "documents": 2, "chunks": 41,
        "prompt_tokens": 1843, "completion_tokens": 512, "total_tokens": 2355,
        "estimated_cost": "0.0042", "created_at": NOW.isoformat(),
    }).execute()


def insert_agent_runs(sid: str) -> None:
    started = NOW - timedelta(seconds=55)
    agents = [
        ("planner", 900, 260, 0, 0, {"plan": ["analyze", "search", "synthesize"]}),
        ("research_agent", 21400, 920, 12, 0, {"queries": 6}),
        ("merge", 300, 180, 12, 0, {"merged": 9}),
        ("answer_agent", 19800, 710, 9, 0, {"citations": 9}),
        ("total", 48321, 2355, 9, 2, {}),
    ]
    for i, (key, latency, tokens, sources, docs, output) in enumerate(agents):
        sb.table("rs_agent_runs").insert({
            "session_id": sid, "agent_key": key, "status": "completed",
            "model": "openai/gpt-4o-mini", "latency_ms": latency, "tokens": tokens,
            "sources": sources, "documents": docs, "output": output,
            "started_at": (started + timedelta(seconds=i * 10)).isoformat(),
            "finished_at": (started + timedelta(seconds=i * 10 + 8)).isoformat(),
            "created_at": NOW.isoformat(),
        }).execute()


def insert_messages(sid: str) -> None:
    user_msg = "Compare RAG with fine-tuning for domain-specific question answering."
    answer = (
        "## RAG vs Fine-tuning for domain-specific Q&A\n\n"
        "Retrieval-Augmented Generation (RAG) grounds answers in fresh external "
        "knowledge without retraining, while fine-tuning bakes behavior into model "
        "weights. For domain-specific question answering, RAG wins on:\n\n"
        "- **Freshness**: knowledge can be updated by swapping the index.\n"
        "- **Transparency**: answers cite retrievable evidence.\n"
        "- **Cost**: no GPU training loop, only inference.\n\n"
        "Fine-tuning remains valuable for style, tool-use formatting, and "
        "vocabulary, but is rarely a substitute for retrieval."
    )
    sb.table("rs_messages").insert([
        {"session_id": sid, "role": "user", "content": user_msg, "metadata": {}, "created_at": (NOW - timedelta(seconds=58)).isoformat()},
        {"session_id": sid, "role": "assistant", "content": answer, "metadata": {"sources": 9}, "created_at": NOW.isoformat()},
    ]).execute()


def insert_documents() -> list[str]:
    ids = []
    for name in SEED_DOCS:
        did = str(uuid4())
        sb.storage.from_("rs_documents").upload(
            f"{UID}/{did}/{name}", MINI_PDF,
            {"content-type": "application/pdf", "upsert": "true"},
        )
        sb.table("rs_documents").insert({
            "id": did, "user_id": UID, "name": name,
            "storage_path": f"{UID}/{did}/{name}", "mime_type": "application/pdf",
            "size_bytes": len(MINI_PDF), "status": "ready", "pages": 1, "chunks": 3,
            "created_at": NOW.isoformat(), "updated_at": NOW.isoformat(),
        }).execute()
        ids.append(did)
    return ids


def insert_reports(sid: str) -> list[str]:
    ids = []
    bodies = {
        SEED_REPORT_TITLES[0]: (
            "## RAG vs Fine-tuning\n\n"
            "We compare retrieval-augmented generation with supervised fine-tuning "
            "across accuracy, freshness, and maintenance cost for domain Q&A.",
            [{"url": "https://arxiv.org/abs/2005.11401", "title": "RAG paper"}, {"url": "https://example.com/rag-vs-ft", "title": "Benchmark"}],
        ),
        SEED_REPORT_TITLES[1]: (
            "## Agent Evaluation Frameworks\n\n"
            "A survey of offline and online evaluation harnesses for multi-agent "
            "research systems, with recommendations for CI integration.",
            [{"url": "https://example.com/agent-eval", "title": "Agent eval survey"}, {"url": "https://example.com/harness", "title": "Harness docs"}],
        ),
        SEED_REPORT_TITLES[2]: (
            "## RAG System Design\n\n"
            "End-to-end design notes: chunking strategy, hybrid retrieval, "
            "re-ranking, and citation-aware answer synthesis.",
            [{"url": "https://example.com/rag-design", "title": "Design doc"}],
        ),
    }
    for title, (content, sources) in bodies.items():
        rid = str(uuid4())
        slug = title.lower().replace(":", "").replace(" ", "-")
        storage_path = f"{UID}/{rid}/{slug}.md"
        sb.storage.from_("rs_reports").upload(
            storage_path, content.encode("utf-8"),
            {"content-type": "text/markdown", "upsert": "true"},
        )
        sb.table("rs_reports").insert({
            "id": rid, "user_id": UID, "session_id": sid, "title": title,
            "content_md": content, "format": "markdown", "status": "ready",
            "is_pinned": False, "is_favorite": False, "storage_path": storage_path,
            "sources": sources,
            "metrics": {"sources": 9, "execution_time_ms": 48321, "token_count": 2355},
            "created_at": NOW.isoformat(), "updated_at": NOW.isoformat(),
        }).execute()
        ids.append(rid)
    return ids


def insert_collection(doc_ids: list[str], report_ids: list[str]) -> None:
    cid = str(uuid4())
    sb.table("rs_collections").insert({
        "id": cid, "user_id": UID, "name": SEED_COLLECTION,
        "description": "Seeded E2E demo workspace",
        "created_at": NOW.isoformat(), "updated_at": NOW.isoformat(),
    }).execute()
    pairs = [(report_ids[0], doc_ids[0]), (report_ids[0], doc_ids[1]), (report_ids[1], doc_ids[1])]
    for report_id, document_id in pairs:
        sb.table("rs_collection_items").insert({
            "collection_id": cid, "report_id": report_id, "document_id": document_id,
            "created_at": NOW.isoformat(),
        }).execute()


def insert_misc() -> None:
    for i, q in enumerate(SEED_SEARCHES):
        sb.table("rs_recent_searches").insert({
            "user_id": UID, "query": q,
            "created_at": (NOW - timedelta(days=i)).isoformat(),
        }).execute()
    sb.table("rs_saved_prompts").insert({
        "user_id": UID, "label": SEED_PROMPT_LABEL,
        "prompt": "Summarize the findings and cite the top sources.",
        "usage_count": 3, "created_at": NOW.isoformat(), "updated_at": NOW.isoformat(),
    }).execute()
    for i, action in enumerate(["collection.created", "document.uploaded", "research.completed"]):
        sb.table("rs_activity_logs").insert({
            "user_id": UID, "action": action,
            "entity_type": "workspace", "entity_id": None,
            "metadata": {"seed": "e2e", "step": i + 1},
            "created_at": (NOW - timedelta(minutes=i)).isoformat(),
        }).execute()


def verify() -> list[str]:
    problems = []
    counts = {
        "sessions": len(sb.table("rs_research_sessions").select("id").eq("user_id", UID).eq("title", SEED_SESSION_TITLE).execute().data),
        "reports": len(sb.table("rs_reports").select("id").eq("user_id", UID).in_("title", SEED_REPORT_TITLES).execute().data),
        "documents": len(sb.table("rs_documents").select("id").eq("user_id", UID).in_("name", SEED_DOCS).execute().data),
        "collections": len(sb.table("rs_collections").select("id").eq("user_id", UID).eq("name", SEED_COLLECTION).execute().data),
        "searches": len(sb.table("rs_recent_searches").select("id").eq("user_id", UID).in_("query", SEED_SEARCHES).execute().data),
        "saved_prompts": len(sb.table("rs_saved_prompts").select("id").eq("user_id", UID).eq("label", SEED_PROMPT_LABEL).execute().data),
    }
    expected = {"sessions": 1, "reports": 3, "documents": 2, "collections": 1, "searches": 5, "saved_prompts": 1}
    for k, want in expected.items():
        if counts[k] != want:
            problems.append(f"{k}: expected {want}, got {counts[k]}")
    return problems


def main() -> None:
    print(f"== E2E seed: user {UID} ({test_email()}) ==")
    rows_deleted, docs_removed = wipe_seed_markers()
    print(f"  removed previous seed copies: {rows_deleted} row(s), {docs_removed} storage object(s)")

    sid = insert_session()
    insert_metrics(sid)
    insert_agent_runs(sid)
    insert_messages(sid)
    doc_ids = insert_documents()
    report_ids = insert_reports(sid)
    insert_collection(doc_ids, report_ids)
    insert_misc()

    problems = verify()
    if problems:
        print("  SEED VERIFY FAILED: " + "; ".join(problems))
        sys.exit(1)
    print(f"  inserted: 1 session, 1 metrics row, 5 agent runs, 2 messages, "
          f"{len(doc_ids)} documents, {len(report_ids)} reports, 1 collection, "
          f"5 recent searches, 1 saved prompt, 3 activity logs")
    print("SEED OK — demo workspace ready (idempotent, safe to re-run).")


if __name__ == "__main__":
    main()
