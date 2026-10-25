"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlignLeft,
  BookOpen,
  ChevronDown,
  Clock3,
  ShieldCheck,
  Sparkles,
  Star,
} from "lucide-react";

import { CONFIDENCE_PILL } from "@/lib/confidence-pill";
import { computeEvidenceScore } from "@/lib/report-citations";
import { confidenceLabel, verdictStars } from "@/lib/trust-scores";
import { cn } from "@/lib/utils";
import type { ReportDetail } from "@/lib/supabase/query";

const EVIDENCE_STYLES: Record<string, string> = {
  Strong: "text-emerald-400",
  Moderate: "text-amber-400",
  Weak: "text-rose-400",
};

export default function ExecutiveSummary({
  report,
  evidence,
  citedCount,
  summaryMd,
}: {
  report: ReportDetail;
  evidence: ReturnType<typeof computeEvidenceScore>;
  citedCount: number;
  summaryMd?: string;
}) {
  const [showFull, setShowFull] = useState(false);

  const wordCount = useMemo(
    () => (report.content_md.match(/\S+/g) || []).length,
    [report.content_md],
  );
  const readMinutes = Math.max(1, Math.round(wordCount / 200));
  const confidence = Math.round(evidence.overall * 10);
  const label = confidenceLabel(confidence);
  const stars = verdictStars(confidence);
  const sourceCount = report.sources?.length ?? 0;

  const stats = [
    {
      label: "Confidence",
      value: `${confidence}%`,
      sub: label,
      icon: ShieldCheck,
      accent: EVIDENCE_STYLES[evidence.label],
    },
    {
      label: "Sources used",
      value: String(sourceCount),
      sub: `${citedCount} cited in text`,
      icon: BookOpen,
      accent: "text-[var(--accent-violet)]",
    },
    {
      label: "Reading time",
      value: `${readMinutes} min`,
      sub: "at 200 wpm",
      icon: Clock3,
      accent: "text-cyan-400",
    },
    {
      label: "Word count",
      value: wordCount.toLocaleString(),
      sub: "report body",
      icon: AlignLeft,
      accent: "text-emerald-400",
    },
  ] as const;

  return (
    <section
      aria-label="Executive summary"
      className="report-summary-enter mb-10 overflow-hidden rounded-2xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface-elevated)_72%,transparent)]"
    >
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border)] bg-gradient-to-r from-[var(--accent-violet)]/10 via-transparent to-cyan-400/5 px-5 py-4 sm:px-6">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent-violet)]/10 px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.12em] text-[var(--accent-violet)]">
          <Sparkles className="h-3 w-3" />
          Executive summary
        </span>
        <span
          className={cn(
            "ml-auto inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[10px] font-semibold",
            CONFIDENCE_PILL[label],
          )}
        >
          <ShieldCheck className="h-3 w-3" />
          {label} confidence
        </span>
      </div>

      <div className="px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-center gap-3">
          <div
            className="flex items-center gap-0.5"
            role="img"
            aria-label={`Overall verdict ${stars} out of ${5} stars`}
          >
            {Array.from({ length: 5 }, (_, i) => (
              <Star
                key={i}
                className={cn(
                  "h-5 w-5",
                  i < stars
                    ? "fill-amber-400 text-amber-400"
                    : "text-[var(--border-strong)]",
                )}
              />
            ))}
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--text-muted)]">
              Overall verdict
            </p>
            <p className={cn("text-sm font-semibold", EVIDENCE_STYLES[evidence.label])}>
              {evidence.label} evidence confidence
            </p>
          </div>
        </div>

        <div className="mt-5 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map(({ label, value, sub, icon: Icon, accent }) => (
            <div
              key={label}
              className="flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface-hover)_25%,transparent)] px-3.5 py-3"
            >
              <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-white/[0.04]">
                <Icon className={cn("h-4 w-4", accent)} />
              </span>
              <span className="min-w-0">
                <span className="block text-[9px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                  {label}
                </span>
                <span className="block truncate text-base font-semibold leading-tight text-[var(--text-primary)]">
                  {value}{" "}
                  <span className={cn("text-xs font-medium", accent)}>{sub}</span>
                </span>
              </span>
            </div>
          ))}
        </div>

        {summaryMd && (
          <div className="mt-5 border-t border-[var(--border)] pt-4">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
              Main finding
            </p>
            <div
              className={cn(
                "prose-custom prose-sm text-[13px]",
                !showFull && "line-clamp-3",
              )}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{summaryMd}</ReactMarkdown>
            </div>
            <button
              type="button"
              aria-expanded={showFull}
              onClick={() => setShowFull((prev) => !prev)}
              className="mt-2.5 inline-flex items-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1 text-[11px] font-medium text-[var(--accent-violet)] transition-colors hover:border-[var(--accent-violet)]/40 hover:bg-[var(--accent-violet)]/5"
            >
              <ChevronDown
                className={cn("h-3 w-3 transition-transform duration-200", showFull && "rotate-180")}
              />
              {showFull ? "Collapse" : "Expand"}
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
