"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Globe2,
  FileText,
  ShieldCheck,
  AlertTriangle,
  TrendingUp,
  Clock,
  ExternalLink,
  BookOpen,
  Star,
  Zap,
} from "lucide-react";
import type { SourceCitation } from "@/lib/types";
import { getTrustScore, authorityStars, getConfidence, getHallucinationRisk } from "@/lib/trust-scores";
import { cn } from "@/lib/utils";

interface SourceInspectorProps {
  source: SourceCitation | null;
  onClose: () => void;
}

function getRiskColor(risk: number): string {
  if (risk <= 5) return "text-emerald-400 bg-emerald-500/10";
  if (risk <= 10) return "text-amber-400 bg-amber-500/10";
  return "text-rose-400 bg-rose-500/10";
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 80) return "text-emerald-400 bg-emerald-500/10";
  if (confidence >= 60) return "text-amber-400 bg-amber-500/10";
  return "text-rose-400 bg-rose-500/10";
}

function getBiasIcon(bias: string) {
  switch (bias) {
    case "low": return <ShieldCheck className="h-3.5 w-3.5" />;
    case "moderate": return <AlertTriangle className="h-3.5 w-3.5" />;
    case "high": return <AlertTriangle className="h-3.5 w-3.5" />;
    default: return null;
  }
}

function getFreshnessColor(freshness: string): string {
  switch (freshness) {
    case "Current": return "text-emerald-400";
    case "Recent": return "text-cyan-400";
    case "Moderate": return "text-amber-400";
    case "Dated": return "text-rose-400";
    default: return "text-[var(--text-muted)]";
  }
}

export default function SourceInspector({ source, onClose }: SourceInspectorProps) {
  const score = source ? getTrustScore(source.url, source.title) : null;
  const confidence = score ? getConfidence(score.authority, score.relevance) : 0;
  const risk = score ? getHallucinationRisk(score.authority) : 0;

  return (
    <AnimatePresence>
      {source && score && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: 380 }}
            animate={{ x: 0 }}
            exit={{ x: 380 }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed inset-y-0 right-0 z-50 w-[380px] overflow-y-auto border-l border-white/[0.08] bg-[var(--bg)] shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-label={`Source Inspector: ${source.title}`}
          >
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-white/[0.06] bg-[var(--bg)]/80 px-4 py-3 backdrop-blur-xl">
              <div className="flex items-center gap-2.5">
                <span className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold text-white shadow-lg",
                  source.source_type === "document"
                    ? "bg-gradient-to-br from-emerald-500 to-emerald-600"
                    : "bg-gradient-to-br from-cyan-500 to-blue-600",
                )}>
                  {source.source_type === "document"
                    ? <FileText className="h-4 w-4" />
                    : <Globe2 className="h-4 w-4" />
                  }
                </span>
                <div>
                  <p className="text-sm font-medium text-[var(--text-primary)]">
                    Source Inspector
                  </p>
                  <p className="text-[9px] text-[var(--text-muted)]">
                    {source.source_type === "document" ? "Document" : "Web source"}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--text-muted)] transition-colors hover:bg-white/[0.06] hover:text-[var(--text-primary)]"
                aria-label="Close inspector"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4 p-4">
              {/* Title & URL */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                <p className="text-[11px] font-medium leading-relaxed text-[var(--text-primary)]">
                  {source.title}
                </p>
                {source.url && (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 flex items-center gap-1 text-[9px] text-cyan-400 transition-colors hover:text-cyan-300"
                  >
                    <ExternalLink className="h-3 w-3" />
                    <span className="truncate">{source.url}</span>
                  </a>
                )}
                {source.relevance && (
                  <p className="mt-2 text-[9px] text-[var(--text-muted)]">
                    {source.relevance}
                  </p>
                )}
              </div>

              {/* Trust Score Card */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                  <ShieldCheck className="h-3 w-3" />
                  Trust Score
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <div>
                    <p className="text-2xl font-bold tabular-nums text-[var(--text-primary)]">
                      {confidence}
                      <span className="text-sm font-normal text-[var(--text-muted)]">%</span>
                    </p>
                    <p className="mt-0.5 text-[9px] text-[var(--text-muted)]">
                      Domain: {score.domain}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] font-medium text-yellow-500">
                      {authorityStars(score.authority)}
                    </p>
                    <p className="mt-0.5 text-[8px] text-[var(--text-muted)]">
                      Authority: {score.authority}/100
                    </p>
                  </div>
                </div>
              </div>

              {/* Breakdown Grid */}
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                  <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                    <TrendingUp className="h-3 w-3" />
                    Authority
                  </div>
                  <div className="mt-2 flex items-baseline gap-1">
                    <span className="text-lg font-bold tabular-nums text-[var(--text-primary)]">
                      {score.authority}
                    </span>
                    <span className="text-[9px] text-[var(--text-muted)]">/100</span>
                  </div>
                </div>
                <div className={cn("rounded-xl border border-white/[0.06] p-3", getFreshnessColor(score.freshness).replace("text-", "bg-").replace("emerald-400", "emerald-500/8").replace("cyan-400", "cyan-500/8").replace("amber-400", "amber-500/8").replace("rose-400", "rose-500/8"))}>
                  <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                    <Clock className="h-3 w-3" />
                    Freshness
                  </div>
                  <p className={cn("mt-2 text-sm font-bold", getFreshnessColor(score.freshness))}>
                    {score.freshness}
                  </p>
                </div>
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                  <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                    {getBiasIcon(score.bias)}
                    Bias
                  </div>
                  <p className={cn(
                    "mt-2 text-sm font-bold capitalize",
                    score.bias === "low" ? "text-emerald-400" :
                    score.bias === "moderate" ? "text-amber-400" : "text-rose-400",
                  )}>
                    {score.bias}
                  </p>
                </div>
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                  <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                    <AlertTriangle className="h-3 w-3" />
                    Risk
                  </div>
                  <span className={cn("mt-2 inline-block rounded-md px-1.5 py-0.5 text-xs font-bold", getRiskColor(risk))}>
                    ~{risk}%
                  </span>
                </div>
              </div>

              {/* Relevant topics */}
              {confidence > 0 && (
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                  <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                    <Zap className="h-3 w-3" />
                    Signal Strength
                  </div>
                  <div className="mt-2 space-y-2">
                    <div>
                      <div className="flex items-center justify-between text-[9px]">
                        <span className="text-[var(--text-muted)]">Authority weight</span>
                        <span className="tabular-nums text-[var(--text-secondary)]">{score.authority}%</span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-emerald-400 transition-all"
                          style={{ width: `${score.authority}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between text-[9px]">
                        <span className="text-[var(--text-muted)]">Relevance</span>
                        <span className="tabular-nums text-[var(--text-secondary)]">{score.relevance}%</span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400 transition-all"
                          style={{ width: `${score.relevance}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Reconstructed badge */}
              <div className="rounded-xl border border-amber-400/20 bg-amber-500/[0.06] p-3">
                <div className="flex items-center gap-1.5 text-[10px] text-amber-400">
                  <BookOpen className="h-3 w-3" />
                  Inferred quality
                </div>
                <p className="mt-1 text-[9px] leading-relaxed text-amber-300/80">
                  Trust metrics are estimated from domain reputation, URL patterns, and title heuristics.
                  They may not reflect the actual content quality of this specific article.
                </p>
              </div>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
