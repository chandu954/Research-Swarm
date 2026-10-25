"""Persistence of completed research runs to Supabase."""

from typing import Any, Dict, Optional

from loguru import logger


def finalize_supabase_run(
    *,
    session_id: str,
    user_id: Optional[str],
    result: Dict[str, Any],
    query: str,
    execution_time: float,
) -> None:
    """Persist a completed research run to Supabase (session, report, metrics).

    Runs after graph execution; failures never affect the API response.
    """
    try:
        from backend.core.supabase import (
            insert_message,
            log_activity,
            save_report,
            save_run_metrics,
            set_report_status,
            set_report_storage_path,
            update_session,
            upload_report_file,
            upsert_agent_run,
        )

        status = result.get("status", "completed")
        answer = result.get("answer")
        sources = result.get("sources", [])
        agent_metrics: Dict[str, Dict[str, Any]] = result.get("agent_metrics", {})

        update_session(
            session_id,
            status="completed" if status == "completed" else status,
            sources_total=len(sources) if sources else 0,
            error=(
                "; ".join(str(e) for e in result.get("errors", []))[:500]
                if status == "failed"
                else None
            ),
        )

        if answer:
            insert_message(session_id=session_id, role="assistant", content=answer)

        metrics = result.get("metrics") or {}
        save_run_metrics(
            session_id=session_id,
            execution_time_ms=round(execution_time * 1000),
            sources_found=len(sources) if sources else 0,
            relevant_sources=metrics.get("relevant_sources", 0),
            documents=len(result.get("document_chunks") or []),
            chunks=metrics.get("chunks", 0),
            prompt_tokens=metrics.get("prompt_tokens", 0),
            completion_tokens=metrics.get("completion_tokens", 0),
            total_tokens=result.get("token_count") or metrics.get("total_tokens", 0),
            estimated_cost=float(
                metrics.get("cost_estimate", result.get("cost_estimate") or 0)
            ),
        )

        if answer and status != "failed":
            from backend.core.supabase import (
                log_activity,
                save_report,
                upload_report_file,
            )

            report = save_report(
                user_id=user_id,
                session_id=session_id,
                title=query[:120],
                content_md=answer,
                sources=sources if sources else None,
                metrics={
                    "execution_time_ms": round(execution_time * 1000),
                    "sources": len(sources),
                    "token_count": result.get("token_count"),
                },
            )
            try:
                storage_path = upload_report_file(
                    user_id=user_id,
                    report_id=report["id"],
                    filename=f"{query[:60].strip().replace(' ', '-')[:60]}.md",
                    content=answer,
                )
                if storage_path:
                    set_report_storage_path(report["id"], storage_path)
            except Exception as exc:  # pragma: no cover - resilience path
                logger.warning(f"report storage upload skipped: {exc}")
                try:
                    set_report_status(report["id"], "failed")
                except Exception as status_exc:  # pragma: no cover
                    logger.warning(f"report status update failed: {status_exc}")
            log_activity(
                user_id=user_id,
                action="research.completed",
                entity_type="research_session",
                entity_id=session_id,
                metadata={"query": query[:200], "sources": len(sources)},
            )

        for agent_key, m in agent_metrics.items():
            if "status" not in m and not m.get("latency_ms"):
                continue
            latency_ms = m.get("latency_ms") or (
                m.get("latency") * 1000 if m.get("latency") else None
            )
            status_key = (
                "completed"
                if m.get("status") in ("ok", None)
                else ("skipped" if m.get("status") == "skipped" else "failed")
            )
            upsert_agent_run(
                session_id=session_id,
                agent_key=agent_key,
                status=status_key,
                model=m.get("model"),
                latency_ms=round(latency_ms) if latency_ms else None,
                tokens=m.get("tokens"),
                sources=m.get("result_count")
                or m.get("source_count")
                or m.get("sources"),
                documents=m.get("chunks_retrieved"),
            )
    except Exception as exc:  # pragma: no cover - resilience path
        logger.warning(f"supabase finalize skipped for {session_id}: {exc}")
