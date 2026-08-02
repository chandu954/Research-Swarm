import { useCallback, useEffect, useRef, useState } from "react";
import { createClient } from "./client";
import { hasSupabaseSession } from "./session";
import type { AgentLog, AgentMetric } from "@/lib/types";

export interface RealtimeReport {
  id: string;
  title: string;
  status: string;
  content_md?: string;
  is_pinned?: boolean;
  created_at?: string;
}

export interface RealtimeDocument {
  id: string;
  name: string;
  status: string;
  pages?: number | null;
  chunks?: number | null;
  size_bytes?: number;
  created_at?: string;
}

export interface RealtimeActivity {
  id: string;
  action: string;
  entity_type?: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
}

interface RealtimeState {
  ready: boolean;
  sessionStatus: string | null;
  sessionTitle: string | null;
  agentLogs: AgentLog[];
  agentMetrics: Record<string, AgentMetric>;
  executionTimeMs: number | undefined;
  sourcesFound: number;
  reports: RealtimeReport[];
  documents: RealtimeDocument[];
  activity: RealtimeActivity[];
}

function agentLogFromRun(row: {
  agent_key: string;
  status: string;
  latency_ms?: number | null;
  created_at?: string;
}): AgentLog {
  return {
    agent: row.agent_key,
    action: "run",
    status: row.status,
    timestamp:
      row.created_at
        ? new Date(row.created_at).getTime() / 1000
        : Date.now() / 1000,
    details:
      row.status === "running"
        ? `${row.agent_key} started`
        : row.latency_ms
          ? `Completed in ${row.latency_ms}ms`
          : row.agent_key,
  };
}

/**
 * Live workspace state driven by Supabase Realtime (Phase 5).
 *
 * Subscribes to postgres_changes for the active research session plus the
 * user's documents, reports and activity. RLS scopes everything to the
 * bridged Supabase identity. Returns no-op state when no session exists.
 */
export function useRealtimeWorkspace(sessionId: string | null) {
  const [ready, setReady] = useState(false);
  const [sessionStatus, setSessionStatus] = useState<string | null>(null);
  const [sessionTitle, setSessionTitle] = useState<string | null>(null);
  const [agentLogs, setAgentLogs] = useState<AgentLog[]>([]);
  const [agentMetrics, setAgentMetrics] = useState<Record<string, AgentMetric>>({});
  const [executionTimeMs, setExecutionTimeMs] = useState<number | undefined>();
  const [sourcesFound, setSourcesFound] = useState(0);
  const [reports, setReports] = useState<RealtimeReport[]>([]);
  const [documents, setDocuments] = useState<RealtimeDocument[]>([]);
  const [activity, setActivity] = useState<RealtimeActivity[]>([]);
  const activeSessionRef = useRef<string | null>(null);

  useEffect(() => {
    if (!hasSupabaseSession()) {
      setReady(false);
      return;
    }
    setReady(true);
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    const supabase = createClient();

    // Reset per-session state when the active session changes.
    setSessionStatus(null);
    setAgentLogs([]);
    setAgentMetrics({});
    setExecutionTimeMs(undefined);
    setSourcesFound(0);
    activeSessionRef.current = sessionId;

    const sessionChannel = supabase
      .channel(`rs-session-${sessionId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "rs_research_sessions",
          filter: `id=eq.${sessionId}`,
        },
        (payload) => {
          const row = payload.new as { status?: string; title?: string } | null;
          if (!row) return;
          if (row.status) setSessionStatus(row.status);
          if (row.title) setSessionTitle(row.title);
        },
      )
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "rs_agent_runs",
          filter: `session_id=eq.${sessionId}`,
        },
        (payload) => {
          const row = payload.new as {
            agent_key: string;
            status: string;
            latency_ms?: number | null;
            model?: string | null;
            tokens?: number | null;
            sources?: number | null;
            documents?: number | null;
            created_at?: string;
          } | null;
          if (!row || !row.agent_key) return;
          const log = agentLogFromRun(row);
          setAgentLogs((prev) => {
            const existing = prev.findIndex(
              (e) => e.agent === log.agent && e.action === log.action,
            );
            if (existing >= 0) {
              const next = [...prev];
              next[existing] = log;
              return next;
            }
            return [...prev, log];
          });
          if (row.status === "completed") {
            setAgentMetrics((prev) => ({
              ...prev,
              [row.agent_key]: {
                latency_ms: row.latency_ms ?? undefined,
                model: row.model ?? undefined,
                tokens: row.tokens ?? undefined,
                source_count: row.sources ?? 0,
                chunks_retrieved: row.documents ?? 0,
                status: "ok",
              } as AgentMetric,
            }));
          }
        },
      )
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "rs_run_metrics",
          filter: `session_id=eq.${sessionId}`,
        },
        (payload) => {
          const row = payload.new as {
            execution_time_ms?: number | null;
            sources_found?: number | null;
          } | null;
          if (!row) return;
          if (row.execution_time_ms != null) {
            setExecutionTimeMs(row.execution_time_ms);
          }
          if (row.sources_found != null) setSourcesFound(row.sources_found);
        },
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(sessionChannel);
      activeSessionRef.current = null;
    };
  }, [sessionId]);

  useEffect(() => {
    if (!ready || !hasSupabaseSession()) return;
    const supabase = createClient();

    const userChannel = supabase
      .channel("rs-workspace")
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "rs_documents",
        },
        (payload) => {
          const row = payload.new as RealtimeDocument | null;
          if (!row) return;
          setDocuments((prev) => {
            const rest = prev.filter((d) => d.id !== row.id);
            return payload.eventType === "DELETE"
              ? rest
              : [row, ...rest];
          });
        },
      )
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "rs_reports",
        },
        (payload) => {
          const row = payload.new as RealtimeReport | null;
          if (!row) return;
          setReports((prev) => {
            const rest = prev.filter((r) => r.id !== row.id);
            return payload.eventType === "DELETE" ? rest : [row, ...rest];
          });
        },
      )
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "rs_activity_logs",
        },
        (payload) => {
          const row = payload.new as RealtimeActivity | null;
          if (!row) return;
          setActivity((prev) => [row, ...prev].slice(0, 20));
        },
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(userChannel);
    };
  }, [ready]);

  return {
    ready,
    sessionStatus,
    sessionTitle,
    agentLogs,
    agentMetrics,
    executionTimeMs,
    sourcesFound,
    reports,
    documents,
    activity,
  } satisfies RealtimeState;
}
