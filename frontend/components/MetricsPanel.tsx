"use client";

import { BarChart3, Database, FileText, Timer } from "lucide-react";
import type { AgentMetric } from "@/lib/types";
import { formatExecutionTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface MetricsPanelProps {
  agentMetrics: Record<string, AgentMetric>;
  executionTime?: number;
  sourceCount: number;
  documentCount: number;
  lastRun?: {
    execution_time_ms?: number | null;
    sources_found?: number | null;
    chunks?: number | null;
    documents?: number | null;
    total_tokens?: number | null;
    estimated_cost?: number | null;
  } | null;
}

const SAMPLE_RUN = {
  execution: "6.4s",
  sources: "21",
  chunks: "41",
  documents: "2",
};

export default function MetricsPanel({
  agentMetrics,
  executionTime,
  sourceCount,
  documentCount,
  lastRun,
}: MetricsPanelProps) {
  const metrics = Object.values(agentMetrics);
  const chunks = metrics.reduce(
    (total, metric) => total + (metric.chunks_retrieved || 0),
    0,
  );
  const model = metrics.find((metric) => metric.model)?.model;
  const hasRun =
    executionTime !== undefined ||
    sourceCount > 0 ||
    documentCount > 0 ||
    metrics.length > 0;

  const items = [
    {
      label: "Execution",
      value: hasRun
        ? formatExecutionTime(executionTime)
        : lastRun?.execution_time_ms != null
          ? formatExecutionTime(lastRun.execution_time_ms / 1000)
          : SAMPLE_RUN.execution,
      icon: Timer,
      color: "violet",
    },
    {
      label: "Sources",
      value: hasRun
        ? sourceCount
        : lastRun?.sources_found != null
          ? String(lastRun.sources_found)
          : SAMPLE_RUN.sources,
      icon: Database,
      color: "cyan",
    },
    {
      label: "Chunks",
      value: hasRun
        ? chunks || "—"
        : lastRun?.chunks != null
          ? String(lastRun.chunks)
          : SAMPLE_RUN.chunks,
      icon: BarChart3,
      color: "emerald",
    },
    {
      label: "Documents",
      value: hasRun
        ? documentCount
        : lastRun?.documents != null
          ? String(lastRun.documents)
          : SAMPLE_RUN.documents,
      icon: FileText,
      color: "orange",
    },
  ] as const;

  return (
    <section>
      <div className="mb-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            Run metrics
          </h2>
          {!hasRun && (
            <span className="rounded bg-white/[0.04] px-1.5 py-0.5 text-[8px] uppercase tracking-wide text-[var(--text-muted)]">
              Last run
            </span>
          )}
        </div>
        <p className="mt-1 truncate text-[10px] text-[var(--text-muted)]">
          {hasRun
            ? model
              ? `Model · ${model}`
              : "This run's performance"
            : lastRun
              ? "Last run · from memory"
              : "Sample · run a research to see yours"}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {items.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="run-metric">
            <Icon className={cn("h-3.5 w-3.5", hasRun ? `metric-${color}` : "text-[var(--text-muted)]")} />
            <span className="text-[9px] text-[var(--text-muted)]">{label}</span>
            <strong className="ml-auto font-mono text-xs font-medium text-[var(--text-primary)]">
              {value}
            </strong>
          </div>
        ))}
      </div>
    </section>
  );
}
