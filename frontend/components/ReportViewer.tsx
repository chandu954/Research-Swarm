"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlignLeft,
  ArrowLeft,
  BookOpen,
  Check,
  ChevronDown,
  Clock3,
  Copy,
  ExternalLink,
  ListOrdered,
  ShieldCheck,
  Sparkles,
  Star,
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
  parseReferences,
  buildUsedInMap,
  countCitationOccurrences,
} from "@/lib/report-citations";
import {
  getTrustScore,
  getConfidence,
  confidenceLabel,
  authorityStars,
  faviconUrl,
  classifySourceType,
  verdictStars,
} from "@/lib/trust-scores";
import { CONFIDENCE_PILL } from "@/lib/confidence-pill";
import type { ExportReportDocument } from "@/lib/export-report";
import ExportMenu from "./ExportMenu";
import SourceTypeBadge from "./SourceTypeBadge";
import { PanelSkeleton } from "./Skeletons";
import { cn } from "@/lib/utils";

const ReportSourceSidebar = dynamic(() => import("./ReportSourceSidebar"), {
  ssr: false,
  loading: () => <PanelSkeleton height={240} />,
});

const EVIDENCE_STYLES: Record<string, string> = {
  Strong: "text-emerald-400",
  Moderate: "text-amber-400",
  Weak: "text-rose-400",
};

function useReadingProgress(): number {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const onScroll = () => {
      const doc = document.documentElement;
      const max = doc.scrollHeight - window.innerHeight;
      setProgress(max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  return progress;
}

function useActiveSection(sectionCount: number): number {
  const [active, setActive] = useState(-1);

  useEffect(() => {
    if (sectionCount === 0) return;
    const elements = document.querySelectorAll<HTMLElement>("[data-section-index]");
    if (elements.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const index = Number((entry.target as HTMLElement).dataset.sectionIndex);
            if (Number.isFinite(index)) setActive(index);
          }
        }
      },
      { rootMargin: "-12% 0px -72% 0px", threshold: 0 },
    );
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [sectionCount]);

  return active;
}

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

function SectionCard({
  level,
  heading,
  number,
  index,
  defaultOpen = true,
  children,
}: {
  level: number;
  heading: string | null;
  number?: string;
  index: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (!heading) {
    return <div className="scroll-mt-28">{children}</div>;
  }
  const HeadingTag = (level === 1 ? "h2" : level === 2 ? "h3" : "h4") as "h2" | "h3" | "h4";

  return (
    <section
      id={`section-${index}`}
      data-section-index={index}
      className="group/section scroll-mt-28 rounded-xl border border-transparent transition-colors hover:border-[var(--border)]"
    >
      <HeadingTag
        className="cursor-pointer select-none px-1 pt-1"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="flex items-center gap-2.5">
          {number && (
            <span className="font-mono text-[10px] font-medium tracking-wide text-[var(--accent-violet)]">
              {number}
            </span>
          )}
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

function TableOfContents({
  toc,
  active,
}: {
  toc: { index: number; heading: string }[];
  active: number;
}) {
  if (toc.length === 0) return null;

  const scrollTo = (index: number) => {
    document
      .getElementById(`section-${index}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <nav
      aria-label="Report sections"
      className="sticky top-0 z-30 -mx-4 mb-8 border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--bg)_90%,transparent)] px-4 py-2.5 backdrop-blur-xl sm:-mx-6 sm:px-6"
    >
      <div className="flex items-center gap-2 overflow-x-auto pb-0.5">
        <ListOrdered className="h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />
        {toc.map(({ index, heading }) => (
          <button
            key={index}
            type="button"
            onClick={() => scrollTo(index)}
            className={cn(
              "shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-medium transition-colors",
              active === index
                ? "border-[var(--accent-violet)]/40 bg-[var(--accent-violet)]/10 text-[var(--accent-violet)]"
                : "border-transparent text-[var(--text-muted)] hover:border-[var(--border)] hover:text-[var(--text-secondary)]",
            )}
          >
            {heading}
          </button>
        ))}
      </div>
    </nav>
  );
}

function ExecutiveSummary({
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

function ReferenceCard({
  entry,
  source,
  usedIn,
}: {
  entry: { index: number; title: string; url?: string; description?: string };
  source?: SourceCitation;
  usedIn: string[];
}) {
  const trust = getTrustScore(source?.url ?? entry.url, source?.title ?? entry.title);
  const confidence = getConfidence(trust.authority, trust.relevance);
  const label = confidenceLabel(confidence);
  const url = source?.url ?? entry.url;
  const iconSrc = faviconUrl(url);
  const type = classifySourceType({ url, provider: source?.provider });

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface-hover)_20%,transparent)] p-3.5 transition-all hover:-translate-y-px hover:border-[var(--accent-violet)]/40 hover:bg-[var(--accent-violet)]/5"
    >
      <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg border border-[var(--border)] bg-white/[0.04]">
        {iconSrc ? (
          <img
            src={iconSrc}
            alt=""
            width={20}
            height={20}
            loading="lazy"
            className="h-5 w-5 object-contain"
          />
        ) : (
          <span className="text-[10px] font-bold text-cyan-300">
            {(entry.title.trim().charAt(0) || "?").toUpperCase()}
          </span>
        )}
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-mono text-[9px] font-medium text-[var(--text-tertiary)]">
            #{String(entry.index).padStart(2, "0")}
          </span>
          <span className="min-w-0 truncate text-[13px] font-semibold text-[var(--text-primary)] transition-colors group-hover:text-[var(--accent-violet)]">
            {entry.title}
          </span>
          <SourceTypeBadge type={type} />
          <span
            className={cn(
              "ml-auto inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[9px] font-medium",
              CONFIDENCE_PILL[label],
            )}
          >
            <ShieldCheck className="h-2.5 w-2.5" />
            {confidence}% · {label}
          </span>
        </span>
        <span className="mt-1 flex items-center gap-1.5 text-[10px] text-[var(--text-tertiary)]">
          <span className="truncate">{url?.replace(/^https?:\/\/(www\.)?/, "") ?? trust.domain}</span>
          <span aria-hidden>·</span>
          <span className="text-yellow-500/60">{authorityStars(trust.authority)}</span>
        </span>
        {entry.description && (
          <span className="mt-1.5 block line-clamp-2 text-[10px] leading-relaxed text-[var(--text-secondary)]">
            {entry.description}
          </span>
        )}
        {usedIn.length > 0 && (
          <span className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="text-[8px] uppercase tracking-wider text-[var(--text-tertiary)]">
              Used in
            </span>
            {usedIn.slice(0, 3).map((heading) => (
              <span
                key={heading}
                className="rounded-sm border border-[var(--border)] bg-white/[0.03] px-1.5 py-0.5 text-[9px] text-[var(--text-secondary)]"
              >
                {heading}
              </span>
            ))}
            {usedIn.length > 3 && (
              <span className="text-[9px] text-[var(--text-tertiary)]">+{usedIn.length - 3}</span>
            )}
          </span>
        )}
      </span>
      <ExternalLink className="mt-1 h-3.5 w-3.5 flex-shrink-0 text-[var(--text-muted)] transition-colors group-hover:text-[var(--accent-violet)]" />
    </a>
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
  const progress = useReadingProgress();
  const activeSection = useActiveSection(sections.length);

  const toc = useMemo(
    () =>
      sections
        .map((section, index) => ({ index, heading: section.heading }))
        .filter((section): section is { index: number; heading: string } => !!section.heading),
    [sections],
  );

  const numberByIndex = useMemo(() => {
    const map = new Map<number, string>();
    let counter = 0;
    for (const [index, section] of sections.entries()) {
      if (section.heading) {
        counter += 1;
        map.set(index, String(counter).padStart(2, "0"));
      }
    }
    return map;
  }, [sections]);

  const summaryMd = useMemo(() => {
    const first = sections[0];
    if (!first || first.heading) return undefined;
    return first.content.replace(/\[Source\s+\d+(?:\s*,\s*\d+)*\]/gi, "").trim();
  }, [sections]);

  const referenceSections = useMemo(
    () =>
      sections
        .map((section, index) => ({ section, index }))
        .filter(({ section }) => /^(references|sources)$/i.test(section.heading ?? "")),
    [sections],
  );

  const usedInMap = useMemo(
    () =>
      buildUsedInMap(
        sources,
        sections.map((section, index) => ({ index, heading: section.heading, content: section.content })),
      ),
    [sections, sources],
  );

  const citationCounts = useMemo(
    () => countCitationOccurrences(report.content_md),
    [report.content_md],
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

  const renderReferences = useCallback(
    (section: { heading: string | null; content: string }) => {
      const entries = parseReferences(section.content);
      return (
        <div className="space-y-2 pt-2">
          {entries.length === 0 ? (
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkCitations]} components={components}>
              {section.content}
            </ReactMarkdown>
          ) : (
            entries.map((entry) => {
              const source = sources[entry.index - 1];
              return (
                <ReferenceCard
                  key={`${entry.index}-${entry.title}`}
                  entry={{ index: entry.index, title: entry.title, url: entry.url, description: entry.description }}
                  source={source}
                  usedIn={usedInMap.get(entry.index) ?? []}
                />
              );
            })
          )}
        </div>
      );
    },
    [sources, components, usedInMap],
  );

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

  const metrics = report.metrics ?? {};

  const exportDocument = useMemo<ExportReportDocument>(
    () => ({
      title: report.title,
      markdown: report.content_md,
      sources,
      metadata: metrics,
    }),
    [report.title, report.content_md, sources, metrics],
  );

  return (
    <div className="report-print-area mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-x-0 top-0 z-50 h-[3px]"
      >
        <div
          className="h-full bg-gradient-to-r from-violet-500 via-cyan-400 to-emerald-400 transition-[width] duration-150"
          style={{ width: `${progress * 100}%` }}
        />
      </div>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <button
          onClick={() => window.history.back()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={handleCopyLink}
            title="Copy link to this report"
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-emerald-400" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
            {copied ? "Copied" : "Copy link"}
          </button>
          <ExportMenu document={exportDocument} />
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
        <h1 className="max-w-3xl text-3xl font-bold leading-tight tracking-tight text-[var(--text-primary)] sm:text-4xl">
          {report.title}
        </h1>
        <p className="mt-3 text-xs text-[var(--text-tertiary)]">
          {sources.length} sources · {cited.length} cited in text
        </p>
      </header>

      <ExecutiveSummary
        report={report}
        evidence={evidence}
        citedCount={cited.length}
        summaryMd={summaryMd}
      />

      <TableOfContents toc={toc} active={activeSection} />

      <div className="grid items-start gap-8 xl:grid-cols-[minmax(0,800px)_320px]">
        <article className="report-prose prose-custom min-w-0 max-w-[820px] space-y-12 text-[16.5px]">
          {sections.map((section, i) => {
            const isReferences = referenceSections.some(({ index }) => index === i);
            return (
              <SectionCard
                key={i}
                level={section.level}
                heading={section.heading}
                number={numberByIndex.get(i)}
                index={i}
                defaultOpen={!isReferences}
              >
                {isReferences ? (
                  renderReferences(section)
                ) : (
                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkCitations]} components={components}>
                    {section.content}
                  </ReactMarkdown>
                )}
              </SectionCard>
            );
          })}
        </article>

        <ReportSourceSidebar
          sources={sources}
          evidence={evidence}
          citationCounts={citationCounts}
        />
      </div>
    </div>
  );
}
