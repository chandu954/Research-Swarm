"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  Bot,
  Check,
  Circle,
  Clock3,
  FileText,
  ListChecks,
  Loader2,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import type { AgentLog, ExecutionStep } from "@/lib/types";
import { cn } from "@/lib/utils";

interface AgentLogsProps {
  logs: AgentLog[];
  plan: ExecutionStep[];
  isRunning: boolean;
}

const previewPlan = [
  { step_id: -1, agent: "research_agent", action: "Search evidence" },
  { step_id: -2, agent: "document_agent", action: "Analyze documents" },
  { step_id: -3, agent: "answer_agent", action: "Synthesize answer" },
];

const agentConfig = {
  planner: { icon: Bot, color: "text-violet-400", label: "Planner" },
  research_agent: {
    icon: Search,
    color: "text-cyan-400",
    label: "Research",
  },
  document_agent: {
    icon: FileText,
    color: "text-emerald-400",
    label: "Document",
  },
  answer_agent: {
    icon: Sparkles,
    color: "text-orange-400",
    label: "Answer",
  },
} as const;

function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp > 10_000_000_000 ? timestamp : timestamp * 1000);
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function AgentLogs({
  logs,
  plan,
  isRunning,
}: AgentLogsProps) {
  const visiblePlan = plan.length > 0 ? plan : previewPlan;

  return (
    <section className="space-y-6">
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <ListChecks className="h-4 w-4 text-violet-400" />
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                Execution plan
              </h2>
            </div>
            <p className="mt-1 text-[10px] text-[var(--text-muted)]">
              {plan.length > 0
                ? `${plan.length} coordinated steps`
                : "Generated dynamically for each question"}
            </p>
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-white/[0.06] bg-white/[0.02]">
          {visiblePlan.map((step, index) => {
            const pendingPreview = plan.length === 0;
            const status = "status" in step ? step.status : "pending";
            return (
              <div
                key={step.step_id}
                className="flex items-center gap-3 border-b border-white/[0.05] px-3 py-2.5 last:border-0"
              >
                <span
                  className={cn(
                    "flex h-5 w-5 items-center justify-center rounded-full border text-[9px] font-medium",
                    status === "completed"
                      ? "border-emerald-400/25 bg-emerald-500/10 text-emerald-300"
                      : status === "running"
                        ? "border-cyan-400/25 bg-cyan-500/10 text-cyan-300"
                        : "border-white/[0.08] bg-white/[0.025] text-[var(--text-muted)]",
                  )}
                >
                  {status === "completed" ? (
                    <Check className="h-3 w-3" />
                  ) : status === "running" ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    index + 1
                  )}
                </span>
                <span
                  className={cn(
                    "min-w-0 flex-1 truncate text-[11px] capitalize",
                    pendingPreview
                      ? "text-[var(--text-muted)]"
                      : "text-[var(--text-secondary)]",
                  )}
                >
                  {step.action.replace(/_/g, " ")}
                </span>
                <span className="text-[9px] capitalize text-[var(--text-muted)]">
                  {pendingPreview ? "Queued" : step.agent.replace(/_agent/g, "")}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              {isRunning ? (
                <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
              ) : (
                <Clock3 className="h-4 w-4 text-cyan-400" />
              )}
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                Agent activity
              </h2>
            </div>
            <p className="mt-1 text-[10px] text-[var(--text-muted)]">
              Timestamped execution events
            </p>
          </div>
          {logs.length > 0 && (
            <span className="font-mono text-[9px] text-[var(--text-muted)]">
              {logs.length} events
            </span>
          )}
        </div>

        <div className="max-h-[320px] overflow-y-auto rounded-xl border border-white/[0.06] bg-white/[0.02] px-3">
          {logs.length === 0 ? (
            <div className="flex items-center gap-2 py-4 text-[10px] text-[var(--text-muted)]">
              <Circle className="h-2.5 w-2.5" />
              Activity will stream here in real time.
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {logs.map((log) => {
                const config =
                  agentConfig[log.agent as keyof typeof agentConfig] ||
                  agentConfig.planner;
                const Icon = config.icon;
                return (
                  <motion.div
                    key={`${log.timestamp}-${log.agent}-${log.action}`}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="flex gap-2.5 border-b border-white/[0.05] py-3 last:border-0"
                  >
                    <Icon
                      className={cn("mt-0.5 h-3.5 w-3.5 flex-shrink-0", config.color)}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-medium text-[var(--text-secondary)]">
                          {config.label}
                        </span>
                        <span className="font-mono text-[8px] text-[var(--text-muted)]">
                          {formatTimestamp(log.timestamp)}
                        </span>
                        {log.status === "failed" && (
                          <X className="ml-auto h-3 w-3 text-rose-400" />
                        )}
                      </div>
                      <p className="mt-1 truncate text-[10px] capitalize text-[var(--text-muted)]">
                        {log.details || log.action.replace(/_/g, " ")}
                      </p>
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          )}
        </div>
      </div>
    </section>
  );
}
