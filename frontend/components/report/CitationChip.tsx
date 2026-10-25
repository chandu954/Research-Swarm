"use client";

import { ShieldCheck } from "lucide-react";

import { CONFIDENCE_PILL } from "@/lib/confidence-pill";
import { sourceEvidenceScore } from "@/lib/report-citations";
import {
  confidenceLabel,
  getConfidence,
  getTrustScore,
} from "@/lib/trust-scores";
import { cn } from "@/lib/utils";
import type { SourceCitation } from "@/lib/types";

export default function CitationChip({
  index,
  source,
  evidence,
}: {
  index: number;
  source?: SourceCitation;
  evidence?: number | null;
}) {
  const score = evidence ?? sourceEvidenceScore(source ?? { source_type: "web", title: "" });
  const trust = getTrustScore(source?.url, source?.title);
  const confidence = getConfidence(trust.authority, trust.relevance);
  const label = confidenceLabel(confidence);

  return (
    <span className="group relative inline-block whitespace-nowrap">
      <span
        data-citation={index}
        role="link"
        tabIndex={0}
        aria-label={`Source ${index}: ${source?.title ?? "unknown source"}`}
        onKeyDown={(event) => {
          if (event.key === "Enter" && source?.url) {
            window.open(source.url, "_blank", "noopener,noreferrer");
          }
        }}
        className="mx-0.5 inline-flex h-4 min-w-4 cursor-pointer items-center justify-center rounded-[5px] border border-[var(--accent-violet)]/40 bg-[var(--accent-violet)]/10 px-1 align-[2px] text-[10px] font-semibold leading-none text-[var(--accent-violet)] outline-none transition-colors group-hover:border-[var(--accent-violet)] group-hover:bg-[var(--accent-violet)]/20 group-focus-within:border-[var(--accent-violet)] group-focus-within:bg-[var(--accent-violet)]/20"
      >
        {index}
      </span>
      <span className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 hidden w-72 -translate-x-1/2 rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)]/95 p-3 shadow-2xl backdrop-blur-xl group-hover:block group-focus-within:block">
        <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-[var(--accent-violet)]">
          Source {index}
        </span>
        <span className="block text-xs font-medium leading-snug text-[var(--text-primary)]">
          {source?.title ?? "Unknown source"}
        </span>
        {source?.url && (
          <span className="mt-1 block truncate text-[10px] text-[var(--text-tertiary)]">
            {source.url}
          </span>
        )}
        <span className="mt-2 flex items-center gap-2 border-t border-[var(--border)] pt-2">
          <span className="flex items-center gap-1 text-[10px] text-[var(--text-secondary)]">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--accent-violet)]" />
            Evidence {score != null ? score.toFixed(1) : "—"}/10
          </span>
          <span className="ml-auto text-[10px] text-[var(--text-tertiary)]">
            {trust.freshness} · {trust.domain}
          </span>
        </span>
        <span
          className={cn(
            "mt-1.5 inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[9px] font-medium",
            CONFIDENCE_PILL[label],
          )}
        >
          <ShieldCheck className="h-2.5 w-2.5" />
          {confidence}% · {label}
        </span>
      </span>
    </span>
  );
}
