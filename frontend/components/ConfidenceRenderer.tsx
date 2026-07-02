"use client";

import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ShieldCheck,
  AlertTriangle,
  TrendingUp,
  Quote,
  Hash,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  splitIntoParagraphs,
  scoreParagraph,
  confidenceColor,
  confidenceLabel,
  type ConfidenceSignal,
} from "@/lib/confidence-engine";

interface ConfidenceRendererProps {
  content: string;
}

function SignalIcon({ signal }: { signal: ConfidenceSignal }) {
  const iconClass = "h-3 w-3";
  switch (signal.type) {
    case "citation":
      return <Quote className={iconClass} />;
    case "hedge":
      return <AlertTriangle className={iconClass} />;
    case "speculation":
      return <Search className={iconClass} />;
    case "quantified":
      return <Hash className={iconClass} />;
    case "source_ref":
      return <TrendingUp className={iconClass} />;
    default:
      return null;
  }
}

export default function ConfidenceRenderer({ content }: ConfidenceRendererProps) {
  const scored = useMemo(() => {
    const paragraphs = splitIntoParagraphs(content);
    return paragraphs.map(scoreParagraph);
  }, [content]);

  const avgConfidence = useMemo(() => {
    if (scored.length === 0) return 0;
    return Math.round(scored.reduce((s, p) => s + p.confidence, 0) / scored.length);
  }, [scored]);

  if (scored.length <= 1) {
    return (
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    );
  }

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[9px] font-medium",
            avgConfidence >= 80
              ? "bg-emerald-500/10 text-emerald-400"
              : avgConfidence >= 60
              ? "bg-amber-500/10 text-amber-400"
              : "bg-rose-500/10 text-rose-400",
          )}
        >
          <ShieldCheck className="h-3 w-3" />
          {avgConfidence}% avg confidence
        </span>
        <span className="text-[9px] text-[var(--text-muted)]">
          {scored.filter((p) => p.confidence >= 80).length}/{scored.length} high-confidence
        </span>
      </div>
      <div className="space-y-2">
        {scored.map((para, i) => (
          <div key={i} className="group relative">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {para.text}
            </ReactMarkdown>
            <div className="mt-1 flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100">
              <div className="flex h-1 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    confidenceColor(para.confidence),
                  )}
                  style={{ width: `${para.confidence}%` }}
                />
              </div>
              <span
                className={cn(
                  "text-[8px] font-medium",
                  para.confidence >= 80
                    ? "text-emerald-400"
                    : para.confidence >= 60
                    ? "text-amber-400"
                    : "text-rose-400",
                )}
              >
                {confidenceLabel(para.confidence)}
              </span>
              {para.signals.length > 0 && (
                <span className="flex gap-1">
                  {para.signals.slice(0, 3).map((signal, j) => (
                    <span
                      key={j}
                      className={cn(
                        "inline-flex items-center gap-0.5 rounded px-1 py-0.5 text-[6px] font-medium",
                        signal.strength > 0
                          ? "bg-emerald-500/10 text-emerald-400"
                          : "bg-rose-500/10 text-rose-400",
                      )}
                      title={signal.label}
                    >
                      <SignalIcon signal={signal} />
                    </span>
                  ))}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
