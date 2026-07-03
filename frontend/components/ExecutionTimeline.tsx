"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  Check,
  Clock3,
  Loader2,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import type { AgentLog, AgentMetric } from "@/lib/types";
import { cn, formatMs } from "@/lib/utils";
import { AGENT_MAP } from "@/lib/agents";

interface ExecutionTimelineProps {
  logs: AgentLog[];
  agentMetrics: Record<string, AgentMetric>;
  isRunning: boolean;
}

const agentDetails: Record<string, string> = {
  planner: "Build execution plan",
  research_agent: "Search and rank sources",
  document_agent: "Retrieve relevant chunks",
  answer_agent: "Connect evidence and cite",
};

function ModelBadge({ name }: { name?: string }) {
  if (!name) return null;
  const short = name.includes(":") ? name.split(":")[0] : name.includes("/") ? name.split("/").pop() || name : name;
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-white/[0.06] bg-white/[0.04] px-1.5 py-0.5 font-mono text-[8px] text-[var(--text-muted)]">
      <Sparkles className="h-2.5 w-2.5" />
      {short}
    </span>
  );
}

interface AgentStepProps {
  agentKey: string;
  log?: AgentLog;
  metrics?: AgentMetric;
  isRunning: boolean;
  isLast: boolean;
}

function AgentStep({
  agentKey,
  log,
  metrics,
  isRunning,
  isLast,
}: AgentStepProps) {
  const meta = AGENT_MAP[agentKey] || AGENT_MAP.planner;
  const Icon = meta.icon;
  const status = log?.status || metrics?.status || (isRunning ? "pending" : "idle");
  const isActive = status === "running";
  const isComplete = status === "completed";
  const isFailed = status === "failed";
  const isSkipped = status === "skipped";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      className="relative flex gap-3"
    >
      {!isLast && (
        <span
          className={cn(
            "absolute left-[15px] top-8 h-[calc(100%-4px)] w-px",
            isComplete ? "bg-emerald-400/35" : "bg-white/[0.07]",
          )}
        />
      )}
      <span
        className={cn(
          "agent-step-icon relative z-10",
          `agent-step-icon-${meta.color}`,
          isActive && "ring-4 ring-cyan-400/10",
          isSkipped && "opacity-40",
        )}
      >
        {isActive ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : isComplete ? (
          <Check className="h-3.5 w-3.5" />
        ) : isFailed ? (
          <X className="h-3.5 w-3.5" />
        ) : isSkipped ? (
          <Icon className="h-3.5 w-3.5" />
        ) : (
          <Icon className="h-3.5 w-3.5" />
        )}
      </span>

      <div
        className={cn(
          "mb-3 min-w-0 flex-1 rounded-xl border px-3 py-2.5 transition-colors",
          isActive
            ? "border-cyan-400/20 bg-cyan-500/[0.055]"
            : "border-white/[0.06] bg-white/[0.022]",
        )}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-xs font-medium text-[var(--text-primary)]">
                {meta.label}
              </p>
              <ModelBadge name={metrics?.model} />
            </div>
              <p className="mt-1 truncate text-[10px] text-[var(--text-muted)]">
                {log?.details || agentDetails[agentKey] || meta.thinking[0]}
            </p>
          </div>
          <div className="flex flex-shrink-0 items-center gap-1.5">
            {metrics?.latency_ms !== undefined && (
              <span className="latency-badge">
                {formatMs(metrics.latency_ms)}
              </span>
            )}
            <span
              className={cn(
                "text-[9px] font-medium capitalize",
                isComplete && "text-emerald-400",
                isActive && "text-cyan-400",
                isFailed && "text-rose-400",
                isSkipped && "text-yellow-500/60",
                !isComplete &&
                  !isActive &&
                  !isFailed &&
                  !isSkipped &&
                  "text-[var(--text-muted)]",
              )}
            >
              {isComplete
                ? "Done"
                : isActive
                  ? "Working"
                  : isFailed
                    ? "Failed"
                    : isSkipped
                      ? "Skipped"
                      : "Queued"}
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default function ExecutionTimeline({
  logs,
  agentMetrics,
  isRunning,
}: ExecutionTimelineProps) {
  const agentKeys = ["planner", "research_agent", "document_agent", "answer_agent"];
  const latestLog = (agent: string) =>
    [...logs].reverse().find((log) => log.agent === agent);
  const completedCount = agentKeys.filter((agent) => {
    const status = latestLog(agent)?.status || agentMetrics[agent]?.status;
    return status === "completed";
  }).length;
  const progress = isRunning
    ? Math.max(12, (completedCount / agentKeys.length) * 100)
    : completedCount > 0
      ? (completedCount / agentKeys.length) * 100
      : 0;

  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-violet-400" />
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              AI workflow
            </h2>
          </div>
          <p className="mt-1 text-[10px] text-[var(--text-muted)]">
            Live agent execution
          </p>
        </div>
        <span
          className={cn(
            "live-badge",
            isRunning ? "text-cyan-300" : "text-[var(--text-muted)]",
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              isRunning ? "animate-pulse bg-cyan-400" : "bg-white/20",
            )}
          />
          {isRunning ? "Live" : completedCount > 0 ? "Complete" : "Ready"}
        </span>
      </div>

      <div className="mb-4 h-1 overflow-hidden rounded-full bg-white/[0.05]">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          className="h-full rounded-full bg-gradient-to-r from-violet-500 via-cyan-400 to-emerald-400"
        />
      </div>

      <AnimatePresence mode="popLayout">
        {agentKeys.map((agentKey, index) => (
          <AgentStep
            key={agentKey}
            agentKey={agentKey}
            log={latestLog(agentKey)}
            metrics={agentMetrics[agentKey]}
            isRunning={isRunning}
            isLast={index === agentKeys.length - 1}
          />
        ))}
      </AnimatePresence>

      {logs.length === 0 && (
        <div className="mt-2 flex items-center gap-2 rounded-lg border border-dashed border-white/[0.07] px-3 py-2.5">
          <Clock3 className="h-3.5 w-3.5 text-[var(--text-muted)]" />
          <p className="text-[10px] text-[var(--text-muted)]">
            Agents will appear here when research begins.
          </p>
        </div>
      )}
    </section>
  );
}
