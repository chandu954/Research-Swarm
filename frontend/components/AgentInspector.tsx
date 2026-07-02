"use client";

import { useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Clock,
  Cpu,
  FileText,
  Globe2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronRight,
  Zap,
  Layers,
  ListChecks,
} from "lucide-react";
import type { AgentLog, AgentMetric } from "@/lib/types";
import { AGENT_MAP, colorStyles } from "@/lib/agents";
import { cn, formatDuration } from "@/lib/utils";

interface AgentInspectorProps {
  agentKey: string | null;
  logs: AgentLog[];
  metrics: AgentMetric | undefined;
  onClose: () => void;
}



export default function AgentInspector({ agentKey, logs, metrics, onClose }: AgentInspectorProps) {
  const config = agentKey ? AGENT_MAP[agentKey] : null;

  const agentLogs = useMemo(
    () => (agentKey ? logs.filter((l) => l.agent === agentKey) : []),
    [agentKey, logs],
  );

  const status = useMemo(() => {
    if (agentLogs.length === 0) return "idle";
    const last = agentLogs[agentLogs.length - 1];
    return last.status === "completed" ? "completed" : last.status === "failed" ? "failed" : "running";
  }, [agentLogs]);

  const firstLog = agentLogs[0];
  const lastLog = agentLogs[agentLogs.length - 1];
  const duration = firstLog && lastLog ? lastLog.timestamp - firstLog.timestamp : metrics?.latency_ms ? metrics.latency_ms / 1000 : 0;

  const steps = useMemo(() => {
    const seen = new Set<string>();
    return agentLogs.filter((l) => {
      const key = l.action;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [agentLogs]);

  return (
    <AnimatePresence>
      {agentKey && config && (
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
            aria-label={`Agent Inspector: ${config.label}`}
          >
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-white/[0.06] bg-[var(--bg)]/80 px-4 py-3 backdrop-blur-xl">
              <div className="flex items-center gap-2.5">
                <span
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br text-[10px] font-bold text-white shadow-lg",
                    config.gradient,
                  )}
                >
                  <config.icon className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-sm font-medium text-[var(--text-primary)]">
                    {config.label}
                  </p>
                  <p className="text-[9px] text-[var(--text-muted)]">
                    Agent Inspector
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
              {/* Status Banner */}
              <div
                className={cn(
                  "flex items-center gap-2 rounded-xl border px-3 py-2.5",
                  status === "completed" && "border-emerald-400/20 bg-emerald-500/[0.06]",
                  status === "running" && "border-cyan-400/20 bg-cyan-500/[0.06]",
                  status === "failed" && "border-rose-400/20 bg-rose-500/[0.06]",
                  status === "idle" && "border-white/[0.06] bg-white/[0.03]",
                )}
              >
                {status === "completed" ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                ) : status === "running" ? (
                  <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
                ) : status === "failed" ? (
                  <AlertCircle className="h-4 w-4 text-rose-400" />
                ) : (
                  <Clock className="h-4 w-4 text-[var(--text-muted)]" />
                )}
                <span className="text-xs font-medium text-[var(--text-primary)]">
                  {status === "completed" && "Completed"}
                  {status === "running" && "Running"}
                  {status === "failed" && "Failed"}
                  {status === "idle" && "Idle"}
                </span>
                {duration > 0 && (
                  <span className="ml-auto text-[10px] tabular-nums text-[var(--text-muted)]">
                    {formatDuration(duration)}
                  </span>
                )}
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                  <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                    <Cpu className="h-3 w-3" />
                    Model
                  </div>
                  <p className="mt-1 truncate text-[11px] font-medium text-[var(--text-primary)]">
                    {metrics?.model || "—"}
                  </p>
                </div>
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                  <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                    <Zap className="h-3 w-3" />
                    Total steps
                  </div>
                  <p className="mt-1 text-[11px] font-medium tabular-nums text-[var(--text-primary)]">
                    {agentLogs.length}
                  </p>
                </div>
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                  <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                    <FileText className="h-3 w-3" />
                    {agentKey === "research_agent" ? "Sources" : agentKey === "document_agent" ? "Chunks" : "Results"}
                  </div>
                  <p className="mt-1 text-[11px] font-medium tabular-nums text-[var(--text-primary)]">
                    {metrics?.source_count ?? metrics?.result_count ?? metrics?.chunks_retrieved ?? metrics?.pdfs_processed ?? "—"}
                  </p>
                </div>
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                  <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                    <Clock className="h-3 w-3" />
                    Latency
                  </div>
                  <p className="mt-1 text-[11px] font-medium tabular-nums text-[var(--text-primary)]">
                    {metrics?.latency_ms ? formatDuration(metrics.latency_ms / 1000) : "—"}
                  </p>
                </div>
              </div>

              {/* Execution Steps */}
              {steps.length > 0 && (
                <div>
                  <div className="mb-2 flex items-center gap-1.5">
                    <ListChecks className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                    <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                      Execution flow
                    </span>
                  </div>
                  <div className="space-y-1 rounded-xl border border-white/[0.06] bg-white/[0.02] p-2">
                    {steps.map((log, i) => (
                      <div
                        key={`${log.action}-${i}`}
                        className="flex items-start gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-white/[0.03]"
                      >
                        <span
                          className={cn(
                            "mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded text-[8px]",
                            log.status === "completed"
                              ? "bg-emerald-500/10 text-emerald-400"
                              : log.status === "failed"
                              ? "bg-rose-500/10 text-rose-400"
                              : "bg-cyan-500/10 text-cyan-400",
                          )}
                        >
                          {log.status === "completed" ? (
                            <CheckCircle2 className="h-3 w-3" />
                          ) : log.status === "failed" ? (
                            <AlertCircle className="h-3 w-3" />
                          ) : (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          )}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] font-medium text-[var(--text-secondary)]">
                            {log.action.replace(/_/g, " ")}
                          </p>
                          {log.details && (
                            <p className="mt-0.5 truncate text-[9px] text-[var(--text-muted)]">
                              {log.details}
                            </p>
                          )}
                        </div>
                        <span className="text-[8px] tabular-nums text-[var(--text-muted)]">
                          {new Date(log.timestamp * 1000).toLocaleTimeString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Full Log Stream */}
              {agentLogs.length > 0 && (
                <div>
                  <div className="mb-2 flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                    <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                      Full log ({agentLogs.length})
                    </span>
                  </div>
                  <div className="max-h-[240px] space-y-0.5 overflow-y-auto rounded-xl border border-white/[0.06] bg-white/[0.02] p-2">
                    {agentLogs.map((log, i) => (
                      <div key={i} className="flex gap-2 py-0.5 text-[9px]">
                        <span className="mt-0.5 h-1 w-1 flex-shrink-0 rounded-full bg-current opacity-30" />
                        <span className="flex-1 text-[var(--text-muted)]">
                          {log.action?.replace(/_/g, " ")}
                        </span>
                        <span className="tabular-nums text-[var(--text-muted)] opacity-50">
                          {new Date(log.timestamp * 1000).toLocaleTimeString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Thinking Messages */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                  <Layers className="h-3 w-3" />
                  Reasoning stages
                </div>
                <div className="mt-2 space-y-1">
                  {config.thinking.map((msg, i) => (
                    <div key={i} className="flex items-center gap-2 text-[10px]">
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          i < agentLogs.length
                            ? "bg-emerald-400"
                            : i === agentLogs.length
                            ? "bg-cyan-400 animate-pulse"
                            : "bg-white/[0.08]",
                        )}
                      />
                      <span
                        className={cn(
                          i <= agentLogs.length
                            ? "text-[var(--text-secondary)]"
                            : "text-[var(--text-muted)]",
                        )}
                      >
                        {msg}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {metrics?.error && (
                <div className="rounded-xl border border-rose-400/20 bg-rose-500/[0.06] p-3">
                  <div className="flex items-center gap-1.5 text-[10px] text-rose-400">
                    <AlertCircle className="h-3 w-3" />
                    Error
                  </div>
                  <p className="mt-1 text-[10px] text-rose-300">{metrics.error}</p>
                </div>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
