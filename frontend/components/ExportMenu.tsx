"use client";

import { useCallback, useState } from "react";
import { Check, FileDown, FileJson, Printer } from "lucide-react";
import {
  buildReportMarkdown,
  exportReport,
  type ExportFormat,
  type ExportReportDocument,
  type ExportHtmlOptions,
} from "@/lib/export-report";
import { cn } from "@/lib/utils";

interface ExportMenuProps {
  document: ExportReportDocument;
  options?: ExportHtmlOptions;
  className?: string;
}

const FORMATS: { format: ExportFormat; label: string; icon: typeof FileDown }[] = [
  { format: "markdown", label: ".md", icon: FileDown },
  { format: "html", label: ".html", icon: FileDown },
  { format: "json", label: ".json", icon: FileJson },
  { format: "pdf", label: "PDF", icon: Printer },
];

// Single export control used by both the in-chat report generator and the
// saved report viewer, so every export button shares styling and behavior.
export default function ExportMenu({ document, options, className }: ExportMenuProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(buildReportMarkdown(document));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable — ignore.
    }
  }, [document]);

  return (
    <div className={cn("flex items-center gap-1", className)}>
      {FORMATS.map(({ format, label, icon: Icon }) => (
        <button
          key={format}
          type="button"
          onClick={() => exportReport(document, format, options)}
          className="export-button"
          aria-label={`Export as ${format === "pdf" ? "PDF (print)" : format.toUpperCase()}`}
          title={`Download as ${format.toUpperCase()}`}
        >
          <Icon className="h-3 w-3" />
          {label}
        </button>
      ))}
      <button
        type="button"
        onClick={handleCopy}
        className="export-button"
        aria-label="Copy report markdown"
        title="Copy as Markdown"
      >
        {copied ? (
          <Check className="h-3 w-3 text-emerald-400" />
        ) : (
          <FileDown className="h-3 w-3" />
        )}
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
