"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import {
  BarChart3,
  BrainCircuit,
  Clock,
  Globe2,
  Gauge,
  Loader2,
  TrendingUp,
  Zap,
} from "lucide-react";
import type { AgentMetric, AgentLog } from "@/lib/types";

interface AnalyticsDashboardProps {
  agentMetrics: Record<string, AgentMetric>;
  logs: AgentLog[];
  executionTime?: number;
  sourceCount: number;
  isRunning: boolean;
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  sub?: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
      <div className="flex items-center justify-between">
        <span className="rounded-lg bg-white/[0.04] p-1.5" style={{ color }}>
          <Icon className="h-3.5 w-3.5" />
        </span>
      </div>
      <p className="mt-2 text-lg font-semibold tabular-nums text-[var(--text-primary)]">
        {value}
      </p>
      <p className="text-[10px] text-[var(--text-muted)]">{label}</p>
      {sub && (
        <p className="mt-0.5 text-[9px] text-[var(--text-muted)]">{sub}</p>
      )}
    </div>
  );
}

export default function AnalyticsDashboard({
  agentMetrics,
  logs,
  executionTime,
  sourceCount,
  isRunning,
}: AnalyticsDashboardProps) {
  const stats = useMemo(() => {
    const agentNames = new Set(logs.map((l) => l.agent));
    const agentsUsed = agentNames.size;

    const completedAgents = new Set(
      logs.filter((l) => l.status === "completed").map((l) => l.agent),
    ).size;

    const totalSteps = logs.length;

    const agentBreakdown = Object.entries(agentMetrics).map(([name, m]) => ({
      name,
      latency: m.latency_ms ? `${(m.latency_ms / 1000).toFixed(1)}s` : "-",
      model: m.model || "unknown",
      sourceCount: m.source_count ?? m.result_count ?? 0,
      status: m.status || "unknown",
    }));

    return { agentsUsed, completedAgents, totalSteps, agentBreakdown };
  }, [agentMetrics, logs]);

  if (!isRunning && Object.keys(agentMetrics).length === 0 && logs.length === 0) {
    return null;
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="mb-3 flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-emerald-400" />
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Session analytics
        </h2>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <StatCard
          icon={BrainCircuit}
          label="Agents used"
          value={`${stats.completedAgents}/${stats.agentsUsed}`}
          sub={stats.agentsUsed > 0 ? `${stats.totalSteps} total steps` : undefined}
          color="#8b5cf6"
        />
        <StatCard
          icon={Clock}
          label="Execution time"
          value={executionTime ? `${executionTime.toFixed(1)}s` : isRunning ? "Running..." : "-"}
          color="#06b6d4"
        />
        <StatCard
          icon={Globe2}
          label="Sources cited"
          value={String(sourceCount)}
          color="#10b981"
        />
        <StatCard
          icon={Gauge}
          label="Avg agent latency"
          value={
            stats.agentBreakdown.length > 0
              ? (() => {
                  const valid = stats.agentBreakdown.filter(
                    (a) => a.latency !== "-",
                  );
                  if (valid.length === 0) return "-";
                  const avg =
                    valid.reduce((sum, a) => {
                      return sum + parseFloat(a.latency);
                    }, 0) / valid.length;
                  return `${avg.toFixed(1)}s`;
                })()
              : "-"
          }
          color="#f59e0b"
        />
      </div>

      {stats.agentBreakdown.length > 0 && (
        <div className="mt-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
          <div className="mb-2 flex items-center gap-1.5">
            <Zap className="h-3 w-3 text-amber-400" />
            <span className="text-[10px] font-medium text-[var(--text-muted)]">
              Per-agent breakdown
            </span>
          </div>
          <div className="space-y-1.5">
            {stats.agentBreakdown.map((agent) => (
              <div key={agent.name} className="flex items-center gap-2 text-[10px]">
                <span className="w-20 truncate text-[var(--text-secondary)]">
                  {agent.name.replace(/_/g, " ")}
                </span>
                <div className="flex-1">
                  <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{
                        width: `${Math.min(
                          (parseFloat(agent.latency) /
                            (executionTime || 1)) *
                            100,
                          100,
                        )}%`,
                      }}
                      transition={{ duration: 0.5 }}
                      className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400"
                    />
                  </div>
                </div>
                <span className="w-12 text-right tabular-nums text-[var(--text-muted)]">
                  {agent.latency}
                </span>
                <span className="w-10 text-right text-[var(--text-muted)]">
                  {agent.sourceCount}s
                </span>
              </div>
            ))}
          </div>
          <div className="mt-1.5 flex justify-between border-t border-white/[0.04] pt-1.5 text-[8px] text-[var(--text-muted)]">
            <span>Agent</span>
            <span className="flex gap-10">
              <span>Latency</span>
              <span>Sources</span>
            </span>
          </div>
        </div>
      )}
    </motion.section>
  );
}
