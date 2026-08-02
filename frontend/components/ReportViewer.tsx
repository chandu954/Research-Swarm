"use client";

import { useCallback, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  Copy,
  ExternalLink,
  FileDown,
  FileText,
  Printer,
} from "lucide-react";
import type { Components } from "react-markdown";
import type { ReportDetail } from "@/lib/supabase/query";
import type { SourceCitation } from "@/lib/types";
import {
  computeEvidenceScore,
  remarkCitations,
  sourceEvidenceScore,
  splitSections,
  extractCitedIndices,
} from "@/lib/report-citations";
import { getTrustScore } from "@/lib/trust-scores";
import { cn } from "@/lib/utils";

const EVIDENCE_STYLES: Record<string, string> = {
  Strong: "text-emerald-400",
  Moderate: "text-amber-400",
  Weak: "text-rose-400",
};

const EVIDENCE_RINGS: Record<string, string> = {
  Strong: "ring-emerald-400/30 border-emerald-400/40",
  Moderate: "ring-amber-400/30 border-amber-400/40",
  Weak: "ring-rose-400/30 border-rose-400/40",
};

function CitationChip({
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
          <span className="text-[10px] text-[var(--text-tertiary)]">
            {source?.provider ?? trust.domain}
          </span>
        </span>
      </span>
    </span>
  );
}

function SectionCard({
  level,
  heading,
  children,
}: {
  level: number;
  heading: string | null;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);
  if (!heading) return <div>{children}</div>;
  const HeadingTag = (level === 1 ? "h2" : level === 2 ? "h3" : "h4") as "h2" | "h3" | "h4";

  return (
    <section className="group/section rounded-xl border border-transparent transition-colors hover:border-[var(--border)]">
      <HeadingTag
        className="cursor-pointer select-none px-1 pt-1"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="flex items-center gap-2">
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-[var(--text-tertiary)] transition-transform duration-200",
              !open && "-rotate-90",
            )}
          />
          {heading}
        </span>
      </HeadingTag>
      {open && <div className="px-1 pb-1">{children}</div>}
    </section>
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

  return (
    <li
      className={cn(
        "rounded-lg border border-[var(--border)] p-3 transition-colors",
        cited && "border-[var(--accent-violet)]/40 bg-[var(--accent-violet)]/5",
      )}
    >
      <div className="flex items-start gap-2.5">
        <span
          className={cn(
            "mt-0.5 inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-md border px-1 text-[10px] font-semibold",
            cited
              ? "border-[var(--accent-violet)] bg-[var(--accent-violet)]/15 text-[var(--accent-violet)]"
              : "border-[var(--border)] text-[var(--text-tertiary)]",
          )}
        >
          {index}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium leading-snug text-[var(--text-primary)]">
            {source.title}
          </p>
          <div className="mt-1 flex items-center gap-2 text-[10px] text-[var(--text-tertiary)]">
            <span>{source.provider ?? getTrustScore(source.url, source.title).domain}</span>
            {source.url && (
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 text-[var(--accent-violet)] hover:underline"
              >
                open <ExternalLink className="h-2.5 w-2.5" />
              </a>
            )}
          </div>
          <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-[var(--bg)]">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[var(--accent-violet)] to-cyan-400"
              style={{ width: `${Math.round((authority / 10) * 100)}%` }}
            />
          </div>
          <div className="mt-1 flex items-center justify-between text-[10px] text-[var(--text-tertiary)]">
            <span>evidence</span>
            <span>{authority.toFixed(1)}/10</span>
          </div>
        </div>
      </div>
    </li>
  );
}

export default function ReportViewer({ report }: { report: ReportDetail }) {
  const [copied, setCopied] = useState(false);

  const sections = useMemo(() => splitSections(report.content_md), [report.content_md]);
  const cited = useMemo(() => extractCitedIndices(report.content_md), [report.content_md]);
  const sources = useMemo(() => report.sources ?? [], [report.sources]);
  const evidence = useMemo(
    () => computeEvidenceScore(sources, cited),
    [sources, cited],
  );

  const components = useMemo<Components>(() => {
    return {
      span: (props) => {
        const raw = (props as { "data-citation"?: string })["data-citation"];
        if (!raw) return <span {...props} />;
        const indices = raw
          .split(",")
          .map(Number)
          .filter((n) => Number.isFinite(n) && n > 0);
        return (
          <span className="whitespace-nowrap">
            {indices.map((idx) => (
              <CitationChip
                key={idx}
                index={idx}
                source={sources[idx - 1]}
                evidence={evidence.perSource[idx - 1] ?? null}
              />
            ))}
          </span>
        );
      },
      h1: ({ children }) => (
        <h1 className="prose-custom prose-headings:mt-0 text-xl font-bold text-[var(--text-primary)]">
          {children}
        </h1>
      ),
    };
  }, [sources, evidence]);

  const createdAt = report.created_at
    ? new Date(report.created_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : null;

  const handleCopyLink = useCallback(() => {
    navigator.clipboard?.writeText(window.location.href).catch(() => {});
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }, []);

  const handleDownloadMarkdown = useCallback(() => {
    const blob = new Blob([report.content_md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${report.title.replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-") || "report"}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }, [report.content_md, report.title]);

  const metrics = report.metrics ?? {};

  return (
    <div className="report-print-area mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <button
          onClick={() => window.history.back()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={handleCopyLink}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-emerald-400" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
            {copied ? "Copied" : "Copy link"}
          </button>
          <button
            onClick={handleDownloadMarkdown}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
          >
            <FileDown className="h-3.5 w-3.5" />
            Markdown
          </button>
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
          >
            <Printer className="h-3.5 w-3.5" />
            PDF
          </button>
        </div>
      </div>

      <header className="mb-8">
        <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px] text-[var(--text-tertiary)]">
          {createdAt && <span>{createdAt}</span>}
          {typeof metrics.execution_time_ms === "number" && (
            <span>· {(metrics.execution_time_ms / 1000).toFixed(1)}s</span>
          )}
          {typeof metrics.sources === "number" && <span>· {metrics.sources} sources</span>}
          {typeof metrics.token_count === "number" && (
            <span>· {metrics.token_count.toLocaleString()} tokens</span>
          )}
        </div>
        <h1 className="max-w-3xl text-2xl font-bold leading-tight tracking-tight text-[var(--text-primary)] sm:text-3xl">
          {report.title}
        </h1>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div
            className={cn(
              "inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 ring-4 ring-transparent",
              EVIDENCE_RINGS[evidence.label],
            )}
          >
            <FileText className="h-4 w-4 text-[var(--accent-violet)]" />
            <span className={cn("text-lg font-bold leading-none", EVIDENCE_STYLES[evidence.label])}>
              {evidence.overall.toFixed(1)}
            </span>
            <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
              {evidence.label} evidence
            </span>
          </div>
          <span className="text-[11px] text-[var(--text-tertiary)]">
            {sources.length} sources · {cited.length} cited in text
          </span>
        </div>
      </header>

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_320px]">
        <article className="prose-custom min-w-0 text-[15px]">
          {sections.map((section, i) => (
            <SectionCard key={i} level={section.level} heading={section.heading}>
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkCitations]} components={components}>
                {section.content}
              </ReactMarkdown>
            </SectionCard>
          ))}
        </article>

        <aside className="print:hidden">
          <div className="sticky top-6">
            <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              Sources
              <span className="rounded-full bg-[var(--accent-violet)]/15 px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent-violet)]">
                {sources.length}
              </span>
            </h2>
            {sources.length === 0 ? (
              <p className="text-xs text-[var(--text-tertiary)]">No sources recorded for this report.</p>
            ) : (
              <ul className="space-y-2.5">
                {sources.map((source, i) => (
                  <SourceRow
                    key={i}
                    index={i + 1}
                    source={source}
                    cited={evidence.cited.includes(i + 1)}
                    evidence={evidence.perSource[i] ?? null}
                  />
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
