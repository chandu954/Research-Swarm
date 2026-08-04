"use client";

import { ClipboardList, FileCheck2, FileText, Globe2 } from "lucide-react";

const steps = [
  {
    icon: ClipboardList,
    color: "violet",
    title: "Plan",
    detail: "The planner turns your question into a research plan",
  },
  {
    icon: Globe2,
    color: "cyan",
    title: "Research",
    detail: "Agents search the web and your PDFs in parallel",
  },
  {
    icon: FileText,
    color: "emerald",
    title: "Synthesize",
    detail: "Evidence is ranked and connected into a cited answer",
  },
  {
    icon: FileCheck2,
    color: "orange",
    title: "Deliver",
    detail: "Export a report, revisit sources, or continue exploring",
  },
] as const;

export default function WorkflowOverview() {
  return (
    <div className="card-glass p-4">
      <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
        How it works
      </p>
      <div className="mt-3 space-y-3">
        {steps.map(({ icon: Icon, color, title, detail }, i) => (
          <div key={title} className="flex gap-3">
            <span className={`agent-step-icon agent-step-icon-${color}`}>
              <Icon className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-2 text-xs font-medium text-[var(--text-primary)]">
                <span className="font-mono text-[9px] text-[var(--text-muted)]">
                  {String(i + 1).padStart(2, "0")}
                </span>
                {title}
              </p>
              <p className="mt-0.5 text-[10px] leading-relaxed text-[var(--text-muted)]">
                {detail}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
