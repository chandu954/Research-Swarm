"use client";

import {
  Check,
  Clock3,
  FileText,
  FolderOpen,
  Github,
  Globe2,
} from "lucide-react";
import type { LiveSession } from "@/lib/supabase/query";
import { cn } from "@/lib/utils";

function timeAgo(iso?: string): string {
  if (!iso) return "";
  const delta = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(delta / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

const tools = [
  { label: "Web", icon: Globe2, color: "text-cyan-400" },
  { label: "PDFs", icon: FileText, color: "text-emerald-400" },
  { label: "GitHub", icon: Github, color: "text-orange-400" },
  { label: "Local files", icon: FolderOpen, color: "text-amber-400" },
] as const;

export default function WorkflowOverview({
  bare = false,
  lastSession,
}: {
  bare?: boolean;
  lastSession?: LiveSession | null;
}) {
  return (
    <div className={cn(!bare && "card-glass p-4")}>
      <p className="text-[13px] font-semibold tracking-tight text-[var(--text-primary)]">
        Assistant
      </p>

      <div className="mt-3 flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400/40" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-400" />
        </span>
        <p className="text-xs font-medium text-[var(--text-primary)]">
          Waiting for a question
        </p>
      </div>
      <p className="mt-1 text-[10px] leading-relaxed text-[var(--text-muted)]">
        The swarm plans, searches and synthesizes automatically the moment you
        ask.
      </p>

      <div className="mt-3 flex items-center gap-2 rounded-lg border border-blue-400/10 bg-blue-500/[0.05] px-2.5 py-2">
        <Clock3 className="h-3.5 w-3.5 flex-shrink-0 text-blue-400" />
        <span className="text-[10px] text-[var(--text-secondary)]">
          Expected duration{" "}
          <strong className="font-semibold text-[var(--text-primary)]">
            2–4 min
          </strong>
        </span>
      </div>

      <p className="mt-3.5 text-[9px] font-medium uppercase tracking-[0.08em] text-[var(--text-muted)]">
        Available tools
      </p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {tools.map(({ label, icon: Icon, color }) => (
          <span
            key={label}
            className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.06] bg-white/[0.03] px-1.5 py-1 text-[9px] text-[var(--text-secondary)]"
          >
            <Check className="h-2.5 w-2.5 text-emerald-400" />
            <Icon className={cn("h-2.5 w-2.5", color)} />
            {label}
          </span>
        ))}
      </div>

      {lastSession && (
        <>
          <p className="mt-3.5 text-[9px] font-medium uppercase tracking-[0.08em] text-[var(--text-muted)]">
            Recent workflow
          </p>
          <button
            type="button"
            className="mt-1.5 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-[var(--surface-hover)]"
          >
            <span
              className={cn(
                "h-1.5 w-1.5 flex-shrink-0 rounded-full",
                lastSession.status === "completed"
                  ? "bg-emerald-400/80"
                  : lastSession.status === "running"
                    ? "animate-pulse bg-amber-400"
                    : "bg-[var(--text-muted)]",
              )}
            />
            <span className="min-w-0 flex-1 truncate text-[10px] text-[var(--text-secondary)]">
              {lastSession.title || lastSession.prompt || "Untitled"}
            </span>
            <span className="shrink-0 text-[9px] text-[var(--text-muted)]">
              {timeAgo(lastSession.updated_at || lastSession.created_at)}
            </span>
          </button>
        </>
      )}
    </div>
  );
}
