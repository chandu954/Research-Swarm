"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Scale, MessageSquare, ChevronDown, ChevronRight,
  CheckCircle2, XCircle, AlertCircle, Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";

export interface DebatePerspective {
  perspective_id: string;
  label: string;
  emoji: string;
  color: string;
  argument: string;
  latency_ms: number;
  status: string;
}

export interface DebateData {
  query: string;
  perspectives: DebatePerspective[];
  judge_verdict: string | null;
  judge_latency_ms: number;
  status: string;
  errors: string[];
}

interface DebateViewProps {
  debate: DebateData;
}

const perspectiveGradients: Record<string, string> = {
  optimist: "from-emerald-500/20 to-emerald-500/5 border-emerald-500/20",
  skeptic: "from-amber-500/20 to-amber-500/5 border-amber-500/20",
  academic: "from-violet-500/20 to-violet-500/5 border-violet-500/20",
  engineer: "from-blue-500/20 to-blue-500/5 border-blue-500/20",
  security: "from-rose-500/20 to-rose-500/5 border-rose-500/20",
  economist: "from-cyan-500/20 to-cyan-500/5 border-cyan-500/20",
  industry: "from-pink-500/20 to-pink-500/5 border-pink-500/20",
};

export default function DebateView({ debate }: DebateViewProps) {
  const [expandedPerspective, setExpandedPerspective] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  if (!debate || debate.status === "failed") {
    return (
      <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 text-sm text-rose-300">
        <AlertCircle className="mr-2 inline h-4 w-4" />
        Debate analysis unavailable.
        {debate?.errors?.length ? <p className="mt-1 text-xs text-rose-400/70">{debate.errors[0]}</p> : null}
      </div>
    );
  }

  const visiblePerspectives = showAll ? debate.perspectives : debate.perspectives.slice(0, 3);
  const hiddenCount = debate.perspectives.length - 3;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-white/[0.06] pb-3">
        <Scale className="h-4 w-4 text-violet-400" />
        <span className="text-sm font-semibold text-white">AI Debate</span>
        <span className="rounded-md bg-violet-500/10 px-1.5 py-0.5 text-[10px] font-medium text-violet-300">
          {debate.perspectives.length} perspectives
        </span>
      </div>

      <p className="text-xs text-gray-500">
        Multiple AI experts analyzed the research from different viewpoints. Judge synthesizes a balanced conclusion.
      </p>

      {/* Perspective Cards */}
      <div className="space-y-2">
        {visiblePerspectives.map((p) => (
          <motion.div
            key={p.perspective_id}
            layout
            className={cn(
              "rounded-xl border bg-gradient-to-b p-3 transition-colors",
              perspectiveGradients[p.perspective_id] || "border-white/[0.08] bg-white/[0.03]",
              expandedPerspective === p.perspective_id ? "ring-1 ring-white/[0.12]" : ""
            )}
          >
            <button
              onClick={() => setExpandedPerspective(
                expandedPerspective === p.perspective_id ? null : p.perspective_id
              )}
              className="flex w-full items-center gap-2"
            >
              <span className="text-lg">{p.emoji}</span>
              <div className="flex-1 text-left">
                <span className="text-sm font-medium text-white">{p.label}</span>
                <div className="flex items-center gap-2 text-[10px] text-gray-500">
                  <span>{p.latency_ms}ms</span>
                  {p.status === "completed" ? (
                    <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                  ) : (
                    <XCircle className="h-3 w-3 text-rose-400" />
                  )}
                </div>
              </div>
              {expandedPerspective === p.perspective_id ? (
                <ChevronDown className="h-3.5 w-3.5 text-gray-500" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-gray-500" />
              )}
            </button>

            <AnimatePresence>
              {expandedPerspective === p.perspective_id && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="mt-3 overflow-hidden"
                >
                  <div className="prose-custom prose-sm max-w-none text-gray-300">
                    <ReactMarkdown>{p.argument}</ReactMarkdown>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ))}
      </div>

      {!showAll && hiddenCount > 0 && (
        <button
          onClick={() => setShowAll(true)}
          className="flex w-full items-center justify-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] py-2 text-xs text-gray-400 transition-colors hover:bg-white/[0.06] hover:text-white"
        >
          <MessageSquare className="h-3 w-3" />
          Show {hiddenCount} more perspective{hiddenCount > 1 ? "s" : ""}
        </button>
      )}

      {/* Judge Verdict */}
      {debate.judge_verdict && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="rounded-xl border border-violet-500/20 bg-gradient-to-b from-violet-500/10 to-violet-500/5 p-4"
        >
          <div className="mb-3 flex items-center gap-2">
            <Scale className="h-4 w-4 text-violet-400" />
            <span className="text-sm font-semibold text-white">Judge&apos;s Synthesis</span>
            <span className="text-[10px] text-gray-500">{debate.judge_latency_ms}ms</span>
          </div>
          <div className="prose-custom prose-sm max-w-none text-gray-300">
            <ReactMarkdown>{debate.judge_verdict}</ReactMarkdown>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
