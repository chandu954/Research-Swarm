"""Migration chain regression tests (H1).

Proves the squashed Alembic chain (0001_initial + 0002_multi_tenant) can
upgrade a fresh database head-to-tail, deterministically, and that the
resulting schema contains the expected tables.
"""
from __future__ import annotations
import sqlite3

REQUIRED_TABLES = {
    "users", "user_devices", "user_sessions", "organizations",
    "organization_members", "workspaces", "workspace_members", "projects",
    "collections", "conversations", "messages", "documents",
    "document_versions", "document_chunks", "research_tasks",
    "knowledge_graph_nodes", "knowledge_graph_edges", "memories",
    "notifications", "audit_logs", "api_keys", "billing_records", "tags",
    "tag_assignments", "bookmarks", "providers",
}


def _upgrade_fresh_db(monkeypatch, tmp_path, name: str) -> str:
    """Run ``alembic upgrade head`` against a fresh SQLite file; return its path."""
    from pathlib import Path
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / name
    # env.py's _db_url() reads backend.db.session.DATABASE_URL at migration
    # runtime, so redirecting the module attribute is enough.
    import backend.db.session as db_session
    monkeypatch.setattr(db_session, "DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(cfg, "head")
    return str(db_path)


def _table_names(db_path: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


class TestMigrationChain:
    def test_upgrade_head_creates_full_schema(self, tmp_path, monkeypatch):
        db_path = _upgrade_fresh_db(monkeypatch, tmp_path, "chain.db")
        tables = _table_names(db_path)
        assert "alembic_version" in tables
        assert REQUIRED_TABLES <= tables, f"missing: {REQUIRED_TABLES - tables}"

    def test_head_version_is_0002(self, tmp_path, monkeypatch):
        db_path = _upgrade_fresh_db(monkeypatch, tmp_path, "head.db")
        conn = sqlite3.connect(db_path)
        try:
            version = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        finally:
            conn.close()
        assert version == "0002"

    def test_chain_upgrades_deterministically(self, tmp_path, monkeypatch):
        first = _table_names(_upgrade_fresh_db(monkeypatch, tmp_path, "a.db"))
        second = _table_names(_upgrade_fresh_db(monkeypatch, tmp_path, "b.db"))
        assert first == second

    def test_chain_ignores_ini_postgres_url(self, tmp_path, monkeypatch):
        """The SQLite target must be used even though alembic.ini declares a
        Postgres URL — env.py must resolve DATABASE_URL at runtime."""
        db_path = _upgrade_fresh_db(monkeypatch, tmp_path, "target.db")
        assert _table_names(db_path)  # non-empty result set means SQLite was used
