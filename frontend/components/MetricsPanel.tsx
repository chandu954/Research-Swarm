"use client";

import { BarChart3, Database, FileText, Timer } from "lucide-react";
import type { AgentMetric } from "@/lib/types";

interface MetricsPanelProps {
  agentMetrics: Record<string, AgentMetric>;
  executionTime?: number;
  sourceCount: number;
  documentCount: number;
}

function formatExecutionTime(seconds?: number): string {
  if (seconds === undefined) return "—";
  return seconds < 1 ? `${Math.round(seconds * 1000)}ms` : `${seconds.toFixed(1)}s`;
}

export default function MetricsPanel({
  agentMetrics,
  executionTime,
  sourceCount,
  documentCount,
}: MetricsPanelProps) {
  const metrics = Object.values(agentMetrics);
  const chunks = metrics.reduce(
    (total, metric) => total + (metric.chunks_retrieved || 0),
    0,
  );
  const model = metrics.find((metric) => metric.model)?.model;

  const items = [
    {
      label: "Execution",
      value: formatExecutionTime(executionTime),
      icon: Timer,
      color: "violet",
    },
    {
      label: "Sources",
      value: sourceCount || "—",
      icon: Database,
      color: "cyan",
    },
    {
      label: "Chunks",
      value: chunks || "—",
      icon: BarChart3,
      color: "emerald",
    },
    {
      label: "Documents",
      value: documentCount || "—",
      icon: FileText,
      color: "orange",
    },
  ] as const;

  return (
    <section>
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Run metrics
        </h2>
        <p className="mt-1 truncate text-[10px] text-[var(--text-muted)]">
          {model ? `Model · ${model}` : "Performance appears after execution"}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {items.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="run-metric">
            <Icon className={`h-3.5 w-3.5 metric-${color}`} />
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
