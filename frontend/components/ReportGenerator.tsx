"use client";

import { useCallback, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileDown,
  ClipboardCopy,
  Check,
  Printer,
  FileText,
} from "lucide-react";
import type { Message, SourceCitation } from "@/lib/types";

interface ReportGeneratorProps {
  query: string;
  messages: Message[];
  sources: SourceCitation[];
}

function generateMarkdown(query: string, messages: Message[], sources: SourceCitation[]): string {
  const parts: string[] = [];

  parts.push(`# Research Report: ${query}`);
  parts.push("");
  parts.push(`> Generated on ${new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}`);
  parts.push("");

  const answer = messages.find((m) => m.role === "assistant" && m.content !== "Thinking..." && m.content !== "...");
  if (answer) {
    parts.push("## Summary");
    parts.push("");
    parts.push(answer.content);
    parts.push("");
  }

  if (sources.length > 0) {
    parts.push("## Sources");
    parts.push("");
    for (const source of sources) {
      parts.push(`- [${source.title}](${source.url || "#"})`);
    }
    parts.push("");
  }

  return parts.join("\n");
}

function generateHTML(query: string, messages: Message[], sources: SourceCitation[]): string {
  const md = generateMarkdown(query, messages, sources);

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Research Report: ${query}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #1a1a2e; }
    h1 { font-size: 2em; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }
    h2 { font-size: 1.4em; margin-top: 32px; }
    blockquote { border-left: 3px solid #8b5cf6; padding-left: 16px; color: #64748b; margin: 0; }
    a { color: #8b5cf6; }
    @media print { body { margin: 0; } }
  </style>
</head>
<body>${md.split("\n").map((line) => {
  if (line.startsWith("# ")) return `<h1>${line.slice(2)}</h1>`;
  if (line.startsWith("## ")) return `<h2>${line.slice(3)}</h2>`;
  if (line.startsWith("> ")) return `<blockquote>${line.slice(2)}</blockquote>`;
  if (line.startsWith("- ")) return `<li>${line.slice(2)}</li>`;
  if (line === "") return "<br>";
  return `<p>${line}</p>`;
}).join("\n")}</body>
</html>`;
}

export default function ReportGenerator({ query, messages, sources }: ReportGeneratorProps) {
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState(false);

  const hasAnswer = messages.some((m) => m.role === "assistant" && m.content !== "Thinking..." && m.content !== "...");

  const handleCopy = useCallback(async () => {
    const md = generateMarkdown(query, messages, sources);
    await navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [query, messages, sources]);

  const handleExportMarkdown = useCallback(() => {
    const md = generateMarkdown(query, messages, sources);
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `research-report-${query.slice(0, 40).replace(/[^a-zA-Z0-9]/g, "-")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [query, messages, sources]);

  const handleExportHTML = useCallback(() => {
    const html = generateHTML(query, messages, sources);
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `research-report-${query.slice(0, 40).replace(/[^a-zA-Z0-9]/g, "-")}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }, [query, messages, sources]);

  const handlePrint = useCallback(() => {
    const html = generateHTML(query, messages, sources);
    const win = window.open("", "_blank");
    if (!win) return;
    win.document.write(html);
    win.document.close();
    win.focus();
    setTimeout(() => win.print(), 500);
  }, [query, messages, sources]);

  if (!hasAnswer) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-4 flex flex-wrap items-center gap-2"
    >
      <span className="mr-1 text-[10px] font-medium text-[var(--text-muted)]">
        <FileText className="mr-1 inline h-3 w-3" />
        Export report
      </span>

      <button
        onClick={handleCopy}
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.06] px-2.5 py-1.5 text-[10px] font-medium text-[var(--text-secondary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--text-primary)]"
      >
        {copied ? (
          <>
            <Check className="h-3 w-3 text-emerald-400" />
            Copied
          </>
        ) : (
          <>
            <ClipboardCopy className="h-3 w-3" />
            Copy
          </>
        )}
      </button>

      <button
        onClick={handleExportMarkdown}
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.06] px-2.5 py-1.5 text-[10px] font-medium text-[var(--text-secondary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--text-primary)]"
      >
        <FileDown className="h-3 w-3" />
        .md
      </button>

      <button
        onClick={handleExportHTML}
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.06] px-2.5 py-1.5 text-[10px] font-medium text-[var(--text-secondary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--text-primary)]"
      >
        <FileDown className="h-3 w-3" />
        .html
      </button>

      <button
        onClick={handlePrint}
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.06] px-2.5 py-1.5 text-[10px] font-medium text-[var(--text-secondary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--text-primary)]"
      >
        <Printer className="h-3 w-3" />
        Print
      </button>
    </motion.div>
  );
}
