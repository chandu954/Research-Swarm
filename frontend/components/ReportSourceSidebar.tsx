"use client";

import { useMemo, useState } from "react";
import { BookOpen, ExternalLink, FileCheck2, ShieldCheck } from "lucide-react";
import type { SourceCitation } from "@/lib/types";
import {
  computeEvidenceScore,
  sourceEvidenceScore,
} from "@/lib/report-citations";
import {
  getTrustScore,
  getConfidence,
  confidenceLabel,
  faviconUrl,
} from "@/lib/trust-scores";
import { CONFIDENCE_PILL } from "@/lib/confidence-pill";
import { cn } from "@/lib/utils";

function Favicon({
  url,
  title,
  className,
}: {
  url?: string;
  title: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const src = useMemo(() => (url && !failed ? faviconUrl(url) : null), [url, failed]);

  if (!src) {
    return (
      <span
        aria-hidden
        className={cn(
          "flex flex-shrink-0 items-center justify-center rounded-lg bg-cyan-500/10 text-[10px] font-bold text-cyan-300",
          className,
        )}
      >
        {(title.trim().charAt(0) || "?").toUpperCase()}
      </span>
    );
  }

  return (
    <img
      src={src}
      alt=""
      width={20}
      height={20}
      loading="lazy"
      onError={() => setFailed(true)}
      className={cn("flex-shrink-0 rounded-md object-contain", className)}
    />
  );
}

function SourceRow({
  index,
  source,
  cited,
  evidence,
}: {
  index: number;
  source: SourceCitation;
  cited: boolean;
  evidence?: number | null;
}) {
  const score = evidence ?? sourceEvidenceScore(source);
  const authority = score != null ? score : getTrustScore(source.url, source.title).authority / 10;
  const trust = getTrustScore(source.url, source.title);
  const confidence = getConfidence(trust.authority, trust.relevance);
  const label = confidenceLabel(confidence);

  return (
    <li
      className={cn(
        "group rounded-lg border p-3 transition-colors",
        cited
          ? "border-[var(--accent-violet)]/40 bg-[var(--accent-violet)]/5"
          : "border-[var(--border)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-hover)]/60",
      )}
    >
      <div className="flex items-start gap-2.5">
        <Favicon url={source.url} title={source.title} className="mt-0.5 h-5 w-5" />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <p className="text-xs font-medium leading-snug text-[var(--text-primary)]">
              <span
                className={cn(
                  "mr-1.5 inline-flex h-4 min-w-4 items-center justify-center rounded-[5px] border px-1 text-[9px] font-semibold leading-none align-[-1px]",
                  cited
                    ? "border-[var(--accent-violet)]/50 bg-[var(--accent-violet)]/15 text-[var(--accent-violet)]"
                    : "border-[var(--border-strong)] text-[var(--text-tertiary)]",
                )}
              >
                {index}
              </span>
              {source.title}
            </p>
            {source.url && (
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Open ${source.title}`}
                title="Open source"
                className="mt-0.5 flex-shrink-0 rounded-md p-1 text-[var(--text-muted)] opacity-60 transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--accent-violet)]"
              >
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-[var(--text-tertiary)]">
            <span className="font-medium text-[var(--text-secondary)]">{trust.domain}</span>
            <span aria-hidden>·</span>
            <span>{trust.freshness}</span>
            <span
              className={cn(
                "ml-auto inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[9px] font-medium",
                CONFIDENCE_PILL[label],
              )}
            >
              <ShieldCheck className="h-2.5 w-2.5" />
              {label}
            </span>
          </div>
          {source.relevance && (
            <p className="mt-1.5 line-clamp-2 text-[10px] leading-relaxed text-[var(--text-secondary)]">
              {source.relevance}
            </p>
          )}
          <div className="mt-2 flex items-center gap-2">
            <div className="h-1 min-w-0 flex-1 overflow-hidden rounded-full bg-[var(--bg)]">
              <div
                className="h-full rounded-full bg-gradient-to-r from-[var(--accent-violet)] to-cyan-400 transition-[width] duration-300"
                style={{ width: `${Math.round((authority / 10) * 100)}%` }}
              />
            </div>
            <span className="flex-shrink-0 text-[9px] tabular-nums text-[var(--text-tertiary)]">
              {authority.toFixed(1)}/10
            </span>
            {cited && (
              <span className="flex flex-shrink-0 items-center gap-0.5 rounded-md bg-[var(--accent-violet)]/10 px-1.5 py-0.5 text-[9px] font-medium text-[var(--accent-violet)]">
                <FileCheck2 className="h-2.5 w-2.5" />
                cited
              </span>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

type SourceSort = "confidence" | "relevance" | "cited";

export default function ReportSourceSidebar({
  sources,
  evidence,
}: {
  sources: SourceCitation[];
  evidence: ReturnType<typeof computeEvidenceScore>;
}) {
  const [sort, setSort] = useState<SourceSort>("confidence");

  const sorted = useMemo(() => {
    const confidenceOf = (source: SourceCitation) => {
      const trust = getTrustScore(source.url, source.title);
      return getConfidence(trust.authority, trust.relevance);
    };
    const relevanceOf = (source: SourceCitation) =>
      source.hybrid_score ?? getTrustScore(source.url, source.title).relevance / 100;

    const list = sources.map((source, i) => ({ source, index: i + 1 }));
    if (sort === "cited") {
      const citedSet = new Set(evidence.cited);
      return [...list].sort(
        (a, b) =>
          Number(citedSet.has(b.index)) - Number(citedSet.has(a.index)) ||
          confidenceOf(b.source) - confidenceOf(a.source),
      );
    }
    if (sort === "relevance") {
      return [...list].sort((a, b) => relevanceOf(b.source) - relevanceOf(a.source));
    }
    return [...list].sort((a, b) => confidenceOf(b.source) - confidenceOf(a.source));
  }, [sources, evidence.cited, sort]);

  return (
    <aside className="print:hidden">
      <div className="sticky top-6">
        <div className="mb-3 flex items-center gap-2">
          <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            <BookOpen className="h-3.5 w-3.5 text-orange-400" />
            Sources
            <span className="rounded-full bg-[var(--accent-violet)]/15 px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent-violet)]">
              {sources.length}
            </span>
          </h2>
          <select
            value={sort}
            onChange={(event) => setSort(event.target.value as SourceSort)}
            aria-label="Sort sources"
            className="ml-auto rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-[10px] text-[var(--text-secondary)] outline-none transition-colors hover:border-[var(--border-strong)] focus:border-violet-400/40"
          >
            <option value="confidence">Confidence</option>
            <option value="relevance">Relevance</option>
            <option value="cited">Cited first</option>
          </select>
        </div>
        {sources.length === 0 ? (
          <p className="text-xs text-[var(--text-tertiary)]">
            No sources recorded for this report.
          </p>
        ) : (
          <ul className="max-h-[calc(100vh-220px)] space-y-2 overflow-y-auto pr-1">
            {sorted.map(({ source, index }) => (
              <SourceRow
                key={index}
                index={index}
                source={source}
                cited={evidence.cited.includes(index)}
                evidence={evidence.perSource[index - 1] ?? null}
              />
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
