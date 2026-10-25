"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import { motion } from "framer-motion";
import {
  BookOpen,
  ExternalLink,
  FileText,
  Library,
  ShieldCheck,
  AlertTriangle,
  TrendingUp,
  Clock,
} from "lucide-react";
import type { SourceCitation } from "@/lib/types";
import {
  getTrustScore,
  authorityStars,
  getConfidence,
  getHallucinationRisk,
  confidenceLabel,
  faviconUrl,
} from "@/lib/trust-scores";
import { useWindowedList } from "@/lib/useWindowedList";

interface SourcesProps {
  sources: SourceCitation[];
  onInspect?: (source: SourceCitation) => void;
}

type SourceSort = "confidence" | "relevance" | "newest";

const FRESHNESS_RANK: Record<string, number> = {
  Current: 4,
  Recent: 3,
  Moderate: 2,
  Dated: 1,
  Unknown: 0,
};

const CONFIDENCE_PILL: Record<string, string> = {
  High: "border-emerald-400/25 bg-emerald-500/10 text-emerald-400",
  Medium: "border-amber-400/25 bg-amber-500/10 text-amber-400",
  Low: "border-rose-400/25 bg-rose-500/10 text-rose-400",
};

function Favicon({ url, title }: { url?: string; title: string }) {
  const src = faviconUrl(url);
  if (!src) {
    return (
      <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-cyan-500/10 text-[11px] font-bold text-cyan-300">
        {(title.trim().charAt(0) || "?").toUpperCase()}
      </span>
    );
  }
  return (
    <Image
      src={src}
      alt=""
      width={20}
      height={20}
      unoptimized
      className="mt-0.5 h-7 w-7 flex-shrink-0 rounded-lg border border-white/[0.06] bg-white/[0.03] object-contain p-1"
    />
  );
}

function TrustBadge({ score }: { score: ReturnType<typeof getTrustScore> }) {
  const confidence = getConfidence(score.authority, score.relevance);
  const label = confidenceLabel(confidence);
  const risk = getHallucinationRisk(score.authority);

  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
      <span
        className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[8px] font-semibold ${CONFIDENCE_PILL[label]}`}
      >
        <ShieldCheck className="h-2.5 w-2.5" />
        {label} · {confidence}%
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
  const [sort, setSort] = useState<SourceSort>("confidence");
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

  const sortedWeb = useMemo(() => {
    const confidenceOf = (source: SourceCitation) => {
      const trust = getTrustScore(source.url, source.title);
      return getConfidence(trust.authority, trust.relevance);
    };
    const list = [...webSources];
    if (sort === "relevance") {
      return list.sort(
        (a, b) =>
          (b.hybrid_score ?? getTrustScore(b.url, b.title).relevance / 100) -
          (a.hybrid_score ?? getTrustScore(a.url, a.title).relevance / 100),
      );
    }
    if (sort === "newest") {
      return list.sort(
        (a, b) =>
          (FRESHNESS_RANK[getTrustScore(b.url, b.title).freshness] ?? 0) -
          (FRESHNESS_RANK[getTrustScore(a.url, a.title).freshness] ?? 0),
      );
    }
    return list.sort((a, b) => confidenceOf(b) - confidenceOf(a));
  }, [webSources, sort]);

  const items = useMemo(
    () => [
      ...sortedWeb.map((source) => ({ kind: "web" as const, source })),
      ...documentSources.map((source) => ({ kind: "document" as const, source })),
    ],
    [sortedWeb, documentSources],
  );

  // Fixed row height (76px content + 12px gap) keeps the windowed list's
  // scroll math exact so long lists never render blank rows.
  const {
    containerRef,
    virtualize,
    start,
    end,
    topPad,
    bottomPad,
    onScroll,
  } = useWindowedList(items, 88);

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
        <>
          {webSources.length > 1 && (
            <div className="mb-2 flex items-center justify-end">
              <select
                value={sort}
                onChange={(event) => setSort(event.target.value as SourceSort)}
                aria-label="Sort sources"
                className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-[9px] text-[var(--text-secondary)] outline-none transition-colors hover:border-[var(--border-strong)] focus:border-violet-400/40"
              >
                <option value="confidence">Sort: Confidence</option>
                <option value="relevance">Sort: Relevance</option>
                <option value="newest">Sort: Newest</option>
              </select>
            </div>
          )}
          <div
            ref={containerRef}
            onScroll={onScroll}
            className="max-h-[420px] overflow-y-auto rounded-xl border border-[var(--border)] bg-white/[0.015]"
          >
            <div
              className="space-y-3 p-2"
              style={{ paddingTop: topPad + 8, paddingBottom: bottomPad + 8 }}
            >
              {items.slice(start, end).map(({ kind, source }) =>
                kind === "web" ? (
                  <div
                    key={`web-${source.url || source.title}`}
                    className={`group flex cursor-pointer items-start gap-2.5 rounded-lg p-2 transition-colors hover:bg-[var(--surface-hover)] ${
                      virtualize ? "h-[76px] overflow-hidden" : ""
                    }`}
                    onClick={() => onInspect?.(source)}
                  >
                    <Favicon url={source.url} title={source.title} />
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
                        {getTrustScore(source.url, source.title).domain}
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
                  </div>
                ) : (
                  <div
                    key={`document-${source.title}-${source.relevance || ""}`}
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
                  </div>
                ),
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
