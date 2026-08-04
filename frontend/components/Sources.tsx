"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import {
  BookOpen,
  ExternalLink,
  FileText,
  Globe2,
  Library,
  ShieldCheck,
  AlertTriangle,
  TrendingUp,
  Clock,
} from "lucide-react";
import type { SourceCitation } from "@/lib/types";
import { getTrustScore, authorityStars, getConfidence, getHallucinationRisk } from "@/lib/trust-scores";
import { useWindowedList } from "@/lib/useWindowedList";

interface SourcesProps {
  sources: SourceCitation[];
  onInspect?: (source: SourceCitation) => void;
}

function TrustBadge({ score }: { score: ReturnType<typeof getTrustScore> }) {
  const confidence = getConfidence(score.authority, score.relevance);
  const risk = getHallucinationRisk(score.authority);

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <span
        className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[8px] font-medium"
        style={{
          backgroundColor: confidence >= 80 ? "rgba(16,185,129,0.1)" : confidence >= 60 ? "rgba(245,158,11,0.1)" : "rgba(239,68,68,0.1)",
          color: confidence >= 80 ? "#34d399" : confidence >= 60 ? "#fbbf24" : "#f87171",
        }}
      >
        <ShieldCheck className="h-2.5 w-2.5" />
        {confidence}% conf.
      </span>
      <span
        className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[8px] font-medium"
        style={{
          backgroundColor: risk <= 5 ? "rgba(16,185,129,0.1)" : risk <= 10 ? "rgba(245,158,11,0.1)" : "rgba(239,68,68,0.1)",
          color: risk <= 5 ? "#34d399" : risk <= 10 ? "#fbbf24" : "#f87171",
        }}
      >
        <AlertTriangle className="h-2.5 w-2.5" />
        ~{risk}% risk
      </span>
      <span className="text-[8px] text-[var(--text-muted)]">
        <Clock className="mr-0.5 inline h-2.5 w-2.5" />
        {score.freshness}
      </span>
    </div>
  );
}

export default function Sources({ sources, onInspect }: SourcesProps) {
  const webSources = sources.filter((source) => source.source_type === "web");
  const documentSources = sources.filter(
    (source) => source.source_type === "document",
  );

  const allConfidence = webSources.map((s) => {
    const score = getTrustScore(s.url, s.title);
    return getConfidence(score.authority, score.relevance);
  });
  const hasAnySources = webSources.length > 0 || documentSources.length > 0;
  const avgConfidence = allConfidence.length
    ? Math.round(allConfidence.reduce((a, b) => a + b, 0) / allConfidence.length)
    : 0;

  const items = useMemo(
    () => [
      ...webSources.map((source) => ({ kind: "web" as const, source })),
      ...documentSources.map((source) => ({ kind: "document" as const, source })),
    ],
    [webSources, documentSources],
  );

  // Fixed row height keeps the windowed list's scroll math exact so long
  // source lists never render blank rows.
  const { containerRef, virtualize, start, end, topPad, bottomPad, onScroll } =
    useWindowedList(items, 92);

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-orange-400" />
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              Sources
            </h2>
          </div>
          <p className="mt-1 text-[10px] text-[var(--text-muted)]">
            Evidence attached to the answer
          </p>
        </div>
        <div className="flex items-center gap-2">
          {avgConfidence > 0 && (
            <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-1 text-[9px] font-medium text-emerald-400">
              <TrendingUp className="h-3 w-3" />
              {avgConfidence}% avg
            </span>
          )}
          {hasAnySources && avgConfidence === 0 && (
            <span className="inline-flex items-center gap-1 rounded-md bg-yellow-500/10 px-2 py-1 text-[9px] font-medium text-yellow-400">
              <TrendingUp className="h-3 w-3" />
              N/A
            </span>
          )}
          {sources.length > 0 && (
            <motion.span
              key={sources.length}
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.2 }}
              className="latency-badge"
            >
              {sources.length} total
            </motion.span>
          )}
        </div>
      </div>

      {sources.length === 0 ? (
        <div className="flex items-center gap-2 rounded-xl border border-dashed border-[var(--border)] px-3 py-4">
          <Library className="h-4 w-4 text-[var(--text-muted)]" />
          <p className="text-[10px] text-[var(--text-muted)]">
            No sources retrieved. Web search and document retrieval found no evidence.
          </p>
        </div>
      ) : (
        <div
          ref={containerRef}
          onScroll={onScroll}
          className="max-h-[420px] overflow-y-auto rounded-xl border border-[var(--border)] bg-white/[0.015]"
        >
          <div className="space-y-4 p-2" style={{ paddingTop: topPad + 8, paddingBottom: bottomPad + 8 }}>
            {items.slice(start, end).map(({ kind, source }) =>
              kind === "web" ? (
                <motion.div
                  key={`web-${source.url || source.title}`}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`group flex cursor-pointer items-start gap-2.5 rounded-lg p-2 transition-colors hover:bg-[var(--surface-hover)] ${
                    virtualize ? "h-[76px] overflow-hidden" : ""
                  }`}
                  onClick={() => onInspect?.(source)}
                >
                  <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400">
                    <Globe2 className="h-3.5 w-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5 flex-wrap">
                      <span className="block truncate text-[11px] text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]">
                        {source.title}
                      </span>
                      <span className="flex-shrink-0 text-[7px] text-yellow-500/60">
                        {authorityStars(getTrustScore(source.url, source.title).authority)}
                      </span>
                      {source.provider && (
                        <span className="inline-flex items-center rounded-sm bg-white/5 px-1 py-0.5 text-[7px] font-medium text-[var(--text-muted)] uppercase tracking-wider">
                          {source.provider}
                        </span>
                      )}
                    </span>
                    <span className="mt-1 block truncate text-[9px] text-[var(--text-muted)]">
                      {source.url}
                    </span>
                    <span className="flex items-center gap-2">
                      <TrustBadge score={getTrustScore(source.url, source.title)} />
                      {source.hybrid_score != null && (
                        <span className="text-[7px] text-[var(--text-muted)]">
                          rel: {source.hybrid_score.toFixed(3)}
                        </span>
                      )}
                    </span>
                  </span>
                  <ExternalLink className="mt-1 h-3 w-3 flex-shrink-0 text-[var(--text-muted)] opacity-0 transition-opacity group-hover:opacity-100" />
                </motion.div>
              ) : (
                <motion.div
                  key={`document-${source.title}-${source.relevance || ""}`}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`flex cursor-pointer items-start gap-2.5 rounded-lg p-2 transition-colors hover:bg-[var(--surface-hover)] ${
                    virtualize ? "h-[76px] overflow-hidden" : ""
                  }`}
                  onClick={() => onInspect?.(source)}
                >
                  <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
                    <FileText className="h-3.5 w-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[11px] text-[var(--text-secondary)]">
                      {source.title}
                    </span>
                    {source.relevance && (
                      <span className="mt-1 block text-[9px] text-[var(--text-muted)]">
                        {source.relevance}
                      </span>
                    )}
                    <TrustBadge score={getTrustScore(undefined, source.title)} />
                  </span>
                </motion.div>
              ),
            )}
          </div>
        </div>
      )}
    </section>
  );
}
