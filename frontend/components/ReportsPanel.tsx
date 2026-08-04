"use client";

import { ArrowUp, FileText } from "lucide-react";
import { useRouter } from "next/navigation";
import type { LiveReport } from "@/lib/supabase/query";

interface ReportsPanelProps {
  reports: LiveReport[];
  onStartResearch?: () => void;
}

function timeAgo(iso?: string): string {
  if (!iso) return "";
  const delta = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(delta / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function ReportsPanel({ reports, onStartResearch }: ReportsPanelProps) {
  const router = useRouter();
  const ready = reports.filter((report) => report.status === "ready");

  return (
    <section className="card-glass p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold tracking-tight text-[var(--text-primary)]">
          <FileText className="h-4 w-4 text-[var(--accent-violet)]" />
          Recent reports
          {ready.length > 0 && (
            <span className="rounded-full bg-[var(--accent-violet)]/15 px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent-violet)]">
              {ready.length}
            </span>
          )}
        </h3>
      </div>

      {ready.length === 0 ? (
        <div className="flex flex-col items-center py-5 text-center">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[color-mix(in_srgb,var(--accent-violet)_10%,transparent)] text-[var(--accent-violet)]">
            <FileText className="h-5 w-5" />
          </span>
          <p className="mt-3 text-sm font-medium text-[var(--text-primary)]">
            No reports yet
          </p>
          <p className="mt-1 max-w-[220px] text-xs leading-relaxed text-[var(--text-muted)]">
            Run a research and export a cited report — it will appear here.
          </p>
          {onStartResearch && (
            <button
              type="button"
              onClick={onStartResearch}
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90"
            >
              Start research
              <ArrowUp className="h-3 w-3 -rotate-90" />
            </button>
          )}
        </div>
      ) : (
        <ul className="space-y-1">
          {ready.map((report) => (
            <li key={report.id}>
              <button
                onClick={() => router.push(`/app/reports/${report.id}`)}
                className="group w-full rounded-lg px-2 py-2 text-left transition-colors hover:bg-[var(--surface-hover)]"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="line-clamp-2 text-[13px] font-medium text-[var(--text-primary)] group-hover:text-[var(--accent-violet)]">
                    {report.title}
                  </span>
                  {report.is_pinned && (
                    <span className="mt-0.5 shrink-0 text-[10px] text-[var(--accent-violet)]">
                      pinned
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-[10px] text-[var(--text-tertiary)]">
                  {timeAgo(report.created_at)}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
