"use client";

import { AnimatePresence, motion } from "framer-motion";
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
  const avgConfidence = allConfidence.length
    ? Math.round(allConfidence.reduce((a, b) => a + b, 0) / allConfidence.length)
    : 0;

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
          {sources.length > 0 && (
            <span className="latency-badge">{sources.length} total</span>
          )}
        </div>
      </div>

      {sources.length === 0 ? (
        <div className="flex items-center gap-2 rounded-xl border border-dashed border-[var(--border)] px-3 py-4">
          <Library className="h-4 w-4 text-[var(--text-muted)]" />
          <p className="text-[10px] text-[var(--text-muted)]">
            Citations will collect here as agents work.
          </p>
        </div>
      ) : (
        <div className="max-h-[420px] space-y-4 overflow-y-auto rounded-xl border border-[var(--border)] bg-white/[0.015] p-2">
          <AnimatePresence initial={false}>
            {webSources.map((source) => {
              const score = getTrustScore(source.url, source.title);
              return (
                <motion.div
                  key={`web-${source.url || source.title}`}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="group flex cursor-pointer items-start gap-2.5 rounded-lg p-2 transition-colors hover:bg-[var(--surface-hover)]"
                  onClick={() => onInspect?.(source)}
                >
                  <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400">
                    <Globe2 className="h-3.5 w-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5">
                      <span className="block truncate text-[11px] text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]">
                        {source.title}
                      </span>
                      <span className="flex-shrink-0 text-[7px] text-yellow-500/60">
                        {authorityStars(score.authority)}
                      </span>
                    </span>
                    <span className="mt-1 block truncate text-[9px] text-[var(--text-muted)]">
                      {source.url}
                    </span>
                    <TrustBadge score={score} />
                  </span>
                  <ExternalLink className="mt-1 h-3 w-3 flex-shrink-0 text-[var(--text-muted)] opacity-0 transition-opacity group-hover:opacity-100" />
                </motion.div>
              );
            })}

            {documentSources.map((source) => {
              const score = getTrustScore(undefined, source.title);
              return (
                <motion.div
                  key={`document-${source.title}-${source.relevance || ""}`}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex cursor-pointer items-start gap-2.5 rounded-lg p-2 transition-colors hover:bg-[var(--surface-hover)]"
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
                    <TrustBadge score={score} />
                  </span>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </section>
  );
}
