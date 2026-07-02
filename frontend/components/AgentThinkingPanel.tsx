"use client";

import { useState, useMemo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Check,
  Loader2,
  Clock,
  List,
  LayoutGrid,
  ChevronDown,
  ChevronRight,
  BrainCircuit,
} from "lucide-react";
import type { AgentLog } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  AGENT_MAP,
  AGENT_ORDER,
  colorStyles,
  bgStyles,
} from "@/lib/agents";

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
  const [viewMode, setViewMode] = useState<"cards" | "timeline">("cards");
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

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
    const thoughts = AGENT_MAP[key]?.thinking;
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

  const agentLogStats = useMemo(() => {
    const stats: Record<string, { count: number; firstTimestamp?: number; lastTimestamp?: number }> = {};
    for (const key of AGENT_ORDER) {
      const agentLogs = logs.filter((l) => l.agent === key);
      if (agentLogs.length > 0) {
        stats[key] = {
          count: agentLogs.length,
          firstTimestamp: agentLogs[0].timestamp,
          lastTimestamp: agentLogs[agentLogs.length - 1].timestamp,
        };
      }
    }
    return stats;
  }, [logs]);

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
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 text-[10px] tabular-nums text-[var(--text-muted)]">
              <Clock className="h-3 w-3" />
              {formatTime(elapsed)}
            </span>
          </div>
        </div>
      </div>

      <div className="px-4 pb-2 pt-3">
        <div className="mb-3 flex items-center justify-between text-[10px]">
          <span className="flex items-center gap-2 text-[var(--text-muted)]">
            {completedCount} of {totalCount} agents complete
            <span className="flex gap-0.5">
              <button
                onClick={() => setViewMode("cards")}
                className={cn("rounded p-0.5 transition-colors", viewMode === "cards" ? "text-[var(--text-secondary)] bg-white/[0.06]" : "hover:text-[var(--text-secondary)]")}
              >
                <LayoutGrid className="h-3 w-3" />
              </button>
              <button
                onClick={() => setViewMode("timeline")}
                className={cn("rounded p-0.5 transition-colors", viewMode === "timeline" ? "text-[var(--text-secondary)] bg-white/[0.06]" : "hover:text-[var(--text-secondary)]")}
              >
                <List className="h-3 w-3" />
              </button>
            </span>
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

      {viewMode === "cards" ? (
        <div className="space-y-0.5 px-3 pb-3">
          <AnimatePresence mode="popLayout">
            {activeAgents.map((key) => {
              const status = getAgentStatus(key);
              const Icon = AGENT_MAP[key]?.icon || BrainCircuit;
              const color = AGENT_MAP[key]?.color || "violet";
              const details = getAgentDetails(key);
              const thinkingMsg = getThinkingMessage(key, status);
              const cs = colorStyles[color] || colorStyles.violet;
              const bs = bgStyles[color] || bgStyles.violet;
              const stats = agentLogStats[key];
              const gradient = AGENT_MAP[key]?.gradient || "from-gray-600 to-gray-600";

              return (
                <motion.div
                  key={key}
                  layout
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <div
                    className={cn(
                      "flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors",
                      status === "running" && bs,
                      status === "completed" && "bg-emerald-500/[0.04]",
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br text-[10px] font-bold text-white shadow-lg",
                        gradient,
                      )}
                    >
                      {status === "completed" ? (
                        <Check className="h-4 w-4" />
                      ) : status === "running" ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Icon className="h-4 w-4" />
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
                          {AGENT_MAP[key]?.label || key}
                        </span>
                        {stats && (
                          <span className="rounded bg-white/[0.04] px-1.5 py-0.5 text-[8px] tabular-nums text-[var(--text-muted)]">
                            {stats.count} steps
                          </span>
                        )}
                        {status === "running" && <ThinkingDots />}
                      </div>
                      <p className="mt-0.5 truncate text-[10px] text-[var(--text-muted)]">
                        {details}
                      </p>
                    </div>

                    <button
                      onClick={() => setExpandedAgent(expandedAgent === key ? null : key)}
                      className="flex-shrink-0 rounded p-0.5 text-[var(--text-muted)] hover:bg-white/[0.06] hover:text-[var(--text-secondary)]"
                    >
                      {expandedAgent === key ? (
                        <ChevronDown className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>

                  {expandedAgent === key && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      className="ml-11 mr-3 mb-2 space-y-0.5 rounded-lg bg-white/[0.02] p-2"
                    >
                      {logs
                        .filter((l) => l.agent === key)
                        .slice(-5)
                        .map((log, i) => (
                          <div key={i} className="flex items-start gap-2 py-0.5">
                            <span className="mt-1 h-1 w-1 flex-shrink-0 rounded-full bg-current opacity-30" />
                            <span className="text-[9px] text-[var(--text-muted)]">
                              {log.action?.replace(/_/g, " ") || log.details}
                            </span>
                          </div>
                        ))}
                    </motion.div>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      ) : (
        <div className="px-3 pb-3">
          <div className="relative ml-1 space-y-0 border-l border-white/[0.06] pl-4">
            {logs.slice(-20).map((log, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.02 }}
                className="relative flex items-start gap-3 py-1"
              >
                <span
                  className={cn(
                    "absolute -left-4 mt-1.5 h-2 w-2 rounded-full border-2",
                    log.status === "completed" ? "border-emerald-400 bg-emerald-400" :
                    log.status === "failed" ? "border-rose-400 bg-rose-400" :
                    "border-cyan-400 bg-cyan-400"
                  )}
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="text-[10px] font-medium text-[var(--text-secondary)]">
                      {AGENT_MAP[log.agent]?.label || log.agent}
                    </span>
                    {log.timestamp && (
                      <span className="text-[8px] text-[var(--text-muted)]">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                    )}
                  </span>
                  <p className="truncate text-[9px] text-[var(--text-muted)]">
                    {log.action?.replace(/_/g, " ") || log.details}
                  </p>
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
