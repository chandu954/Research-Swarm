"use client";

import { useCallback, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowLeft, Check, Copy } from "lucide-react";
import type { Components } from "react-markdown";
import type { ReportDetail } from "@/lib/supabase/query";
import {
  buildUsedInMap,
  computeEvidenceScore,
  countCitationOccurrences,
  extractCitedIndices,
  parseReferences,
  remarkCitations,
  splitSections,
} from "@/lib/report-citations";
import type { ExportReportDocument } from "@/lib/export-report";
import { useActiveSection, useReadingProgress } from "@/lib/useReportReading";
import CitationChip from "./report/CitationChip";
import ExecutiveSummary from "./report/ExecutiveSummary";
import ReferenceCard from "./report/ReferenceCard";
import ReportToc from "./report/ReportToc";
import SectionCard from "./report/SectionCard";
import ExportMenu from "./ExportMenu";
import { PanelSkeleton } from "./Skeletons";

const ReportSourceSidebar = dynamic(() => import("./ReportSourceSidebar"), {
  ssr: false,
  loading: () => <PanelSkeleton height={240} />,
});

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

  const metrics = report.metrics;

  const exportDocument = useMemo<ExportReportDocument>(
    () => ({
      title: report.title,
      markdown: report.content_md,
      sources,
      metadata: metrics ?? {},
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
          {typeof metrics?.execution_time_ms === "number" && (
            <span>· {(metrics.execution_time_ms / 1000).toFixed(1)}s</span>
          )}
          {typeof metrics?.sources === "number" && <span>· {metrics.sources} sources</span>}
          {typeof metrics?.token_count === "number" && (
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

      <ReportToc toc={toc} active={activeSection} />

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
