"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  BrainCircuit,
  Check,
  FileText,
  Globe2,
  Loader2,
  Search,
  Sparkles,
  Clock,
} from "lucide-react";
import type { AgentLog } from "@/lib/types";
import { cn } from "@/lib/utils";

const agentMeta: Record<string, { label: string; icon: React.ElementType; color: string; thinking: string[] }> = {
  planner: {
    label: "Planner",
    icon: BrainCircuit,
    color: "violet",
    thinking: [
      "Analyzing your query...",
      "Breaking down into subtasks...",
      "Identifying relevant sources...",
      "Building execution plan...",
      "Prioritizing research directions...",
    ],
  },
  research_agent: {
    label: "Web Research",
    icon: Globe2,
    color: "cyan",
    thinking: [
      "Searching the web...",
      "Extracting key information...",
      "Ranking search results...",
      "Summarizing findings...",
      "Cross-referencing sources...",
    ],
  },
  document_agent: {
    label: "Document Analysis",
    icon: FileText,
    color: "emerald",
    thinking: [
      "Loading documents...",
      "Chunking text content...",
      "Computing embeddings...",
      "Retrieving relevant passages...",
      "Reranking by relevance...",
    ],
  },
  answer_agent: {
    label: "Answer Synthesis",
    icon: Sparkles,
    color: "orange",
    thinking: [
      "Gathering evidence...",
      "Structuring the answer...",
      "Citing sources...",
      "Fact-checking claims...",
      "Polishing final response...",
    ],
  },
  verifier: {
    label: "Verifier",
    icon: Search,
    color: "rose",
    thinking: [
      "Checking conflicting claims...",
      "Validating source credibility...",
      "Cross-referencing facts...",
    ],
  },
  merge: {
    label: "Merge",
    icon: BrainCircuit,
    color: "amber",
    thinking: [
      "Combining research results...",
      "Reconciling differences...",
    ],
  },
};

const AGENT_ORDER = ["planner", "research_agent", "document_agent", "answer_agent"];

const colorStyles: Record<string, { running: string; done: string }> = {
  violet: {
    running: "border-violet-400/20 bg-violet-500/10 text-violet-300",
    done: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300",
  },
  cyan: {
    running: "border-cyan-400/20 bg-cyan-500/10 text-cyan-300",
    done: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300",
  },
  emerald: {
    running: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300",
    done: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300",
  },
  orange: {
    running: "border-orange-400/20 bg-orange-500/10 text-orange-300",
    done: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300",
  },
  rose: {
    running: "border-rose-400/20 bg-rose-500/10 text-rose-300",
    done: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300",
  },
  amber: {
    running: "border-amber-400/20 bg-amber-500/10 text-amber-300",
    done: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300",
  },
};

const bgStyles: Record<string, string> = {
  violet: "bg-violet-500/[0.06]",
  cyan: "bg-cyan-500/[0.06]",
  emerald: "bg-emerald-500/[0.06]",
  orange: "bg-orange-500/[0.06]",
  rose: "bg-rose-500/[0.06]",
  amber: "bg-amber-500/[0.06]",
};

interface AgentThinkingPanelProps {
  logs: AgentLog[];
  isRunning: boolean;
  elapsed: number;
}

function ThinkingDots() {
  return (
    <span className="inline-flex gap-0.5">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-1 w-1 rounded-full bg-current opacity-60"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.25 }}
        />
      ))}
    </span>
  );
}

export default function AgentThinkingPanel({ logs, isRunning, elapsed }: AgentThinkingPanelProps) {
  const activeAgents = AGENT_ORDER.filter((key) => {
    const agentLogs = logs.filter((l) => l.agent === key);
    return agentLogs.length > 0 || isRunning;
  });

  const getAgentStatus = (key: string): "idle" | "running" | "completed" | "failed" => {
    const agentLogs = logs.filter((l) => l.agent === key);
    if (agentLogs.length === 0) return "idle";
    const last = agentLogs[agentLogs.length - 1];
    if (last.status === "completed") return "completed";
    if (last.status === "failed") return "failed";
    return "running";
  };

  const getAgentDetails = (key: string): string => {
    const agentLogs = logs.filter((l) => l.agent === key);
    if (agentLogs.length === 0) return "Waiting...";
    const last = agentLogs[agentLogs.length - 1];
    return last.details || last.action?.replace(/_/g, " ") || "Working...";
  };

  const getThinkingMessage = (key: string, status: string): string => {
    if (status === "completed") return "Complete";
    if (status === "failed") return "Failed";
    const thoughts = agentMeta[key]?.thinking;
    if (!thoughts) return "Working...";
    const logCount = logs.filter((l) => l.agent === key).length;
    return thoughts[Math.min(logCount, thoughts.length - 1)];
  };

  const completedCount = activeAgents.filter((a) => getAgentStatus(a) === "completed").length;
  const totalCount = activeAgents.length;
  const progress = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  const formatTime = (seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  };

  if (!isRunning && completedCount === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-5 overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.03]"
    >
      <div className="border-b border-white/[0.06] px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="relative flex h-6 w-6 items-center justify-center">
              {isRunning && (
                <span className="absolute inset-0 animate-ping rounded-full bg-cyan-400/20" />
              )}
              <Loader2 className={cn("h-4 w-4", isRunning ? "animate-spin text-cyan-400" : "text-emerald-400")} />
            </span>
            <span className="text-sm font-medium text-[var(--text-primary)]">
              {isRunning ? "AI agents working" : "Research complete"}
            </span>
          </div>
          <span className="flex items-center gap-1 text-[10px] tabular-nums text-[var(--text-muted)]">
            <Clock className="h-3 w-3" />
            {formatTime(elapsed)}
          </span>
        </div>
      </div>

      <div className="px-4 pb-2 pt-3">
        <div className="mb-3 flex items-center justify-between text-[10px]">
          <span className="text-[var(--text-muted)]">
            {completedCount} of {totalCount} agents complete
          </span>
          <span className="font-medium tabular-nums text-[var(--text-secondary)]">
            {Math.round(progress)}%
          </span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="h-full rounded-full bg-gradient-to-r from-violet-500 via-cyan-400 to-emerald-400"
          />
        </div>
      </div>

      <div className="space-y-0.5 px-3 pb-3">
        <AnimatePresence mode="popLayout">
          {activeAgents.map((key) => {
            const status = getAgentStatus(key);
            const Icon = agentMeta[key]?.icon || BrainCircuit;
            const color = agentMeta[key]?.color || "violet";
            const details = getAgentDetails(key);
            const thinkingMsg = getThinkingMessage(key, status);
            const cs = colorStyles[color] || colorStyles.violet;
            const bs = bgStyles[color] || bgStyles.violet;

            return (
              <motion.div
                key={key}
                layout
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors",
                  status === "running" && bs,
                  status === "completed" && "bg-emerald-500/[0.04]",
                )}
              >
                <span
                  className={cn(
                    "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg border text-[10px]",
                    status === "running" && cs.running,
                    status === "completed" && cs.done,
                    status === "idle" && "border-white/[0.06] bg-white/[0.03] text-[var(--text-muted)]",
                  )}
                >
                  {status === "completed" ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : status === "running" ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Icon className="h-3.5 w-3.5" />
                  )}
                </span>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "text-xs font-medium",
                        status === "running" && "text-[var(--text-primary)]",
                        status === "completed" && "text-emerald-300",
                        status === "idle" && "text-[var(--text-muted)]",
                      )}
                    >
                      {agentMeta[key]?.label || key}
                    </span>
                    {status === "running" && <ThinkingDots />}
                  </div>
                  <p className="mt-0.5 truncate text-[10px] text-[var(--text-muted)]">
                    {status === "running" ? details : thinkingMsg}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
