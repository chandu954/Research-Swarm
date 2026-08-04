"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText,
  TrendingUp,
  Layout,
  BookOpen,
} from "lucide-react";
import type { Message, SourceCitation } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { ExportReportDocument } from "@/lib/export-report";
import ExportMenu from "./ExportMenu";

type ReportTemplate = "executive" | "technical" | "swot";

interface ReportGeneratorProps {
  query: string;
  messages: Message[];
  sources: SourceCitation[];
}

interface TemplateConfig {
  key: ReportTemplate;
  label: string;
  icon: typeof FileText;
  description: string;
}

const TEMPLATES: TemplateConfig[] = [
  { key: "executive", label: "Executive Summary", icon: BookOpen, description: "Concise overview with key findings and recommendations" },
  { key: "technical", label: "Technical Report", icon: Layout, description: "Deep dive with methodology, analysis, and appendix" },
  { key: "swot", label: "SWOT Analysis", icon: TrendingUp, description: "Strengths, weaknesses, opportunities, and threats" },
];

function findAnswer(messages: Message[]): string {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role === "assistant" && m.content !== "Thinking..." && m.content !== "...") {
      return m.content || "";
    }
  }
  return "";
}

function extractSections(text: string): { heading: string; content: string }[] {
  const sections: { heading: string; content: string }[] = [];
  const lines = text.split("\n");
  let current: { heading: string; content: string[] } | null = null;

  for (const line of lines) {
    const headingMatch = line.match(/^#{1,3}\s+(.+)/);
    if (headingMatch) {
      if (current) sections.push({ heading: current.heading, content: current.content.join("\n").trim() });
      current = { heading: headingMatch[1], content: [] };
    } else if (current) {
      current.content.push(line);
    }
  }
  if (current) sections.push({ heading: current.heading, content: current.content.join("\n").trim() });

  return sections;
}

// Template generators return report body markdown only; the shared export
// module owns the title header, date, generator credit, and source appendix.
function generateExecutiveMD(answer: string, sources: SourceCitation[]): string {
  const sections = extractSections(answer);
  const firstLines = answer.split("\n").filter((l) => l.trim()).slice(0, 5).join(" ");

  const parts: string[] = [];
  parts.push("## Key Findings");
  parts.push("");
  parts.push(firstLines.slice(0, 500));
  parts.push("");

  if (sections.length > 0) {
    parts.push("## Section Overview");
    parts.push("");
    for (const s of sections) {
      parts.push(`- **${s.heading}** — ${s.content.slice(0, 120).replace(/\n/g, " ")}...`);
    }
    parts.push("");
  }

  return parts.join("\n");
}

function generateTechnicalMD(answer: string): string {
  const sections = extractSections(answer);
  const parts: string[] = [];

  if (sections.length > 0) {
    parts.push("## Table of Contents");
    for (const [i, s] of sections.entries()) {
      parts.push(`${i + 1}. [${s.heading}](#section-${i})`);
    }
    parts.push("");
  }

  for (const [i, s] of sections.entries()) {
    parts.push(`<a id="section-${i}"></a>`);
    parts.push(`## ${i + 1}. ${s.heading}`);
    parts.push("");
    parts.push(s.content);
    parts.push("");
  }

  parts.push("## Methodology");
  parts.push("");
  parts.push("This report was generated using ResearchSwarm, a multi-agent AI research system.");
  parts.push("The system employs specialized agents for planning, web research, document analysis, and answer synthesis.");
  parts.push("Sources are scored by domain authority, freshness, and relevance.");

  return parts.join("\n");
}

function generateSWOTMD(answer: string): string {
  const sections = extractSections(answer);

  const strengths = sections.filter((s) =>
    /advantage|benefit|strength|strong|effective|improvement|success|leading/i.test(s.content)
  ).map((s) => s.heading);
  const weaknesses = sections.filter((s) =>
    /limitation|challenge|weakness|drawback|concern|issue|gap|lack/i.test(s.content)
  ).map((s) => s.heading);
  const opportunities = sections.filter((s) =>
    /opportunity|potential|future|emerging|growth|trend|innovation/i.test(s.content)
  ).map((s) => s.heading);
  const threats = sections.filter((s) =>
    /risk|threat|danger|competition|regulatory|barrier|concern/i.test(s.content)
  ).map((s) => s.heading);

  const parts: string[] = [];
  parts.push("## Strengths");
  parts.push("");
  if (strengths.length > 0) {
    for (const s of strengths) parts.push(`- ${s}`);
  } else {
    parts.push("*No explicit strengths identified in the source material.*");
  }
  parts.push("");

  parts.push("## Weaknesses");
  parts.push("");
  if (weaknesses.length > 0) {
    for (const s of weaknesses) parts.push(`- ${s}`);
  } else {
    parts.push("*No explicit weaknesses identified in the source material.*");
  }
  parts.push("");

  parts.push("## Opportunities");
  parts.push("");
  if (opportunities.length > 0) {
    for (const s of opportunities) parts.push(`- ${s}`);
  } else {
    parts.push("*No explicit opportunities identified in the source material.*");
  }
  parts.push("");

  parts.push("## Threats");
  parts.push("");
  if (threats.length > 0) {
    for (const s of threats) parts.push(`- ${s}`);
  } else {
    parts.push("*No explicit threats identified in the source material.*");
  }
  parts.push("");

  parts.push("---");
  parts.push("");
  parts.push("### Full Analysis");
  parts.push("");
  parts.push(answer);

  return parts.join("\n");
}

export default function ReportGenerator({ query, messages, sources }: ReportGeneratorProps) {
  const [template, setTemplate] = useState<ReportTemplate>("executive");
  const [includeCover, setIncludeCover] = useState(true);
  const [includeToc, setIncludeToc] = useState(true);
  const [showOptions, setShowOptions] = useState(false);

  const answer = useMemo(() => findAnswer(messages), [messages]);
  const hasAnswer = answer.length > 0;

  const md = useMemo(() => {
    switch (template) {
      case "executive": return generateExecutiveMD(answer, sources);
      case "technical": return generateTechnicalMD(answer);
      case "swot": return generateSWOTMD(answer);
    }
  }, [template, answer, sources]);

  const document = useMemo<ExportReportDocument>(
    () => ({
      title: query,
      markdown: md,
      sources,
      metadata: { template, sources: sources.length },
    }),
    [query, md, sources, template],
  );

  if (!hasAnswer) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-4 space-y-2"
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-[10px] font-medium text-[var(--text-muted)]">
          <FileText className="mr-1 inline h-3 w-3" />
          Export
        </span>

        {TEMPLATES.map((t) => (
          <button
            key={t.key}
            onClick={() => { setTemplate(t.key); setShowOptions(true); }}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[10px] font-medium transition-colors",
              template === t.key
                ? "border-cyan-400/30 bg-cyan-500/10 text-cyan-300"
                : "border-white/[0.06] text-[var(--text-secondary)] hover:bg-white/[0.06] hover:text-[var(--text-primary)]",
            )}
            title={t.description}
          >
            <t.icon className="h-3 w-3" />
            {t.label}
          </button>
        ))}

        <div className="ml-auto">
          <ExportMenu document={document} options={{ cover: includeCover, toc: includeToc }} />
        </div>
      </div>

      <AnimatePresence>
        {showOptions && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="flex flex-wrap items-center gap-3 overflow-hidden rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2"
          >
            <span className="text-[9px] font-medium text-[var(--text-muted)]">Options:</span>
            <label className="flex cursor-pointer items-center gap-1.5">
              <input
                type="checkbox"
                checked={includeCover}
                onChange={(e) => setIncludeCover(e.target.checked)}
                className="h-3 w-3 rounded border-white/[0.1] bg-white/[0.04] text-cyan-500"
              />
              <span className="text-[10px] text-[var(--text-secondary)]">Cover page</span>
            </label>
            <label className="flex cursor-pointer items-center gap-1.5">
              <input
                type="checkbox"
                checked={includeToc}
                onChange={(e) => setIncludeToc(e.target.checked)}
                className="h-3 w-3 rounded border-white/[0.1] bg-white/[0.04] text-cyan-500"
              />
              <span className="text-[10px] text-[var(--text-secondary)]">Table of Contents</span>
            </label>
            <span className="text-[8px] text-[var(--text-muted)]">
              {template === "technical" ? "Sections auto-linked" : template === "swot" ? "Auto-classified by keyword" : "Condensed format"}
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
