"use client";

import { ArrowUp, FileText } from "lucide-react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import type { LiveReport } from "@/lib/supabase/query";
import { cn } from "@/lib/utils";

interface ReportsPanelProps {
  reports: LiveReport[];
  onStartResearch?: () => void;
  bare?: boolean;
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

export default function ReportsPanel({ reports, onStartResearch, bare = false }: ReportsPanelProps) {
  const router = useRouter();
  const ready = reports.filter((report) => report.status === "ready");

  return (
    <section className={cn(!bare && "card-glass p-4")}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-[13px] font-semibold tracking-tight text-[var(--text-primary)]">
          <FileText className="h-[18px] w-[18px] text-[var(--accent-violet)]" />
          Recent reports
          {ready.length > 0 && (
            <motion.span
              key={ready.length}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.2 }}
              className="rounded-full bg-[var(--accent-violet)]/15 px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent-violet)]"
            >
              {ready.length}
            </motion.span>
          )}
        </h3>
      </div>

      {ready.length === 0 ? (
        <div className="relative flex flex-col items-center py-6 text-center">
          <span className="relative flex h-12 w-12 items-center justify-center rounded-full bg-[color-mix(in_srgb,var(--accent-violet)_10%,transparent)] text-[var(--accent-violet)]">
            <span className="absolute inset-0 rounded-full border border-[var(--accent-violet)]/20" />
            <FileText className="h-6 w-6" />
          </span>
          <p className="mt-3 text-[15px] font-semibold text-[var(--text-primary)]">
            Your research reports will appear here
          </p>
          <p className="mt-1.5 max-w-[250px] text-xs leading-relaxed text-[var(--text-muted)]">
            Every completed research automatically generates a fully cited
            report.
          </p>
          {onStartResearch && (
            <button
              type="button"
              onClick={onStartResearch}
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white transition-all hover:-translate-y-px hover:opacity-90"
            >
              Start Research
              <ArrowUp className="h-3 w-3 -rotate-90" />
            </button>
          )}
        </div>
      ) : (
        <ul className="space-y-1">
          <AnimatePresence initial={false}>
            {ready.map((report) => (
              <motion.li
                key={report.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
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
                  <div className="mt-0.5 text-[11px] text-[var(--text-tertiary)]">
                    {timeAgo(report.created_at)}
                  </div>
                </button>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </section>
  );
}
