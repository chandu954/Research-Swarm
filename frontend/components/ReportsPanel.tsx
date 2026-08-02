"use client";

import { FileText } from "lucide-react";
import { useRouter } from "next/navigation";
import type { LiveReport } from "@/lib/supabase/query";
import { cn } from "@/lib/utils";

interface ReportsPanelProps {
  reports: LiveReport[];
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

export default function ReportsPanel({ reports }: ReportsPanelProps) {
  const router = useRouter();
  const ready = reports.filter((report) => report.status === "ready");

  return (
    <section className="panel rounded-xl border p-4" style={{ borderColor: "var(--border)" }}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          <FileText className="h-3.5 w-3.5" />
          Reports
          {ready.length > 0 && (
            <span className="rounded-full bg-[var(--accent-violet)]/15 px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent-violet)]">
              {ready.length}
            </span>
          )}
        </h3>
      </div>

      {ready.length === 0 ? (
        <p className="text-xs leading-relaxed text-[var(--text-tertiary)]">
          No reports yet — run a research to generate one.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {ready.map((report) => (
            <li key={report.id}>
              <button
                onClick={() => router.push(`/app/reports/${report.id}`)}
                className="group w-full rounded-lg border border-transparent px-2 py-1.5 text-left transition-colors hover:border-[var(--border)] hover:bg-[var(--surface-hover)]"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="line-clamp-2 text-xs font-medium text-[var(--text-primary)] group-hover:text-[var(--accent-violet)]">
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
