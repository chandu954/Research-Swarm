import { useCallback, useEffect, useState } from "react";
import { createClient } from "./client";
import { hasSupabaseSession } from "./session";

export interface LiveSession {
  id: string;
  title: string;
  prompt: string;
  status: string;
  mode: string;
  sources_total: number;
  created_at: string;
  updated_at: string;
}

export interface LiveCollection {
  id: string;
  name: string;
  description: string;
}

export interface LiveDocument {
  id: string;
  name: string;
  status: string;
  pages?: number | null;
  chunks?: number | null;
  size_bytes?: number;
  created_at?: string;
}

export interface LiveReport {
  id: string;
  title: string;
  status: string;
  is_pinned?: boolean;
  created_at?: string;
}

export interface LiveRunMetrics {
  execution_time_ms?: number | null;
  sources_found?: number | null;
  relevant_sources?: number | null;
  documents?: number | null;
  chunks?: number | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  estimated_cost?: number | null;
  session_title?: string | null;
}

interface LiveWorkspace {
  ready: boolean;
  sessions: LiveSession[];
  collections: LiveCollection[];
  documents: LiveDocument[];
  reports: LiveReport[];
  lastMetrics: LiveRunMetrics | null;
  refresh: () => void;
}

/**
 * Initial live load for the workspace panels (Phase 7).
 * Realtime (useRealtimeWorkspace) keeps the data moving afterwards; this
 * hook supplies the first paint from the same RLS-scoped tables.
 */
export function useLiveWorkspace(): LiveWorkspace {
  const [ready, setReady] = useState(false);
  const [sessions, setSessions] = useState<LiveSession[]>([]);
  const [collections, setCollections] = useState<LiveCollection[]>([]);
  const [documents, setDocuments] = useState<LiveDocument[]>([]);
  const [reports, setReports] = useState<LiveReport[]>([]);
  const [lastMetrics, setLastMetrics] = useState<LiveRunMetrics | null>(null);
  const [nonce, setNonce] = useState(0);

  const load = useCallback(async () => {
    if (!hasSupabaseSession()) {
      setReady(false);
      return;
    }
    setReady(true);
    const supabase = createClient();

    const [sessionsRes, collectionsRes, documentsRes, reportsRes, metricsRes] =
      await Promise.all([
        supabase
          .from("rs_research_sessions")
          .select("id,title,prompt,status,mode,sources_total,created_at,updated_at")
          .order("updated_at", { ascending: false })
          .limit(8),
        supabase
          .from("rs_collections")
          .select("id,name,description")
          .order("created_at", { ascending: false })
          .limit(20),
        supabase
          .from("rs_documents")
          .select("id,name,status,pages,chunks,size_bytes,created_at")
          .order("created_at", { ascending: false })
          .limit(30),
        supabase
          .from("rs_reports")
          .select("id,title,status,is_pinned,created_at")
          .order("created_at", { ascending: false })
          .limit(30),
        supabase
          .from("rs_run_metrics")
          .select(
            "execution_time_ms,sources_found,relevant_sources,documents,chunks,prompt_tokens,completion_tokens,total_tokens,estimated_cost,rs_research_sessions(title)",
          )
          .order("created_at", { ascending: false })
          .limit(1),
      ]);

    if (!sessionsRes.error) setSessions(sessionsRes.data ?? []);
    if (!collectionsRes.error) setCollections(collectionsRes.data ?? []);
    if (!documentsRes.error) setDocuments(documentsRes.data ?? []);
    if (!reportsRes.error) setReports(reportsRes.data ?? []);
    if (!metricsRes.error && metricsRes.data?.length) {
      const row = metricsRes.data[0];
      setLastMetrics({
        execution_time_ms: row.execution_time_ms,
        sources_found: row.sources_found,
        relevant_sources: row.relevant_sources,
        documents: row.documents,
        chunks: row.chunks,
        prompt_tokens: row.prompt_tokens,
        completion_tokens: row.completion_tokens,
        total_tokens: row.total_tokens,
        estimated_cost: row.estimated_cost,
        session_title:
          (row.rs_research_sessions as { title?: string } | null)?.title ?? null,
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  return { ready, sessions, collections, documents, reports, lastMetrics, refresh };
}
