"use client";

import type { RefObject } from "react";
import { motion } from "framer-motion";
import { ArrowUp, FileCheck2, FolderOpen } from "lucide-react";

import { cn } from "@/lib/utils";
import type { LiveCollection, LiveReport, LiveSession } from "@/lib/supabase/query";
import {
  capabilities,
  suggestions,
  timeAgo,
} from "@/lib/chat-presets";
import { Composer, type ComposerProps } from "./Composer";

export interface RecentItem {
  key: string;
  title: string;
  meta: string;
  prompt: string;
  status: string;
}

interface ChatEmptyStateProps {
  lastSession: LiveSession | null;
  greeting: string;
  firstName: string;
  recentItems: RecentItem[];
  recentCollections: LiveCollection[];
  reportList: LiveReport[];
  readyReports: LiveReport[];
  composerProps: Omit<ComposerProps, "variant">;
  onSend: (query: string) => void;
  setInput: (value: string) => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  router: { push: (href: string) => void };
  isRunning: boolean;
}

export default function ChatEmptyState({
  lastSession,
  greeting,
  firstName,
  recentItems,
  recentCollections,
  reportList,
  readyReports,
  composerProps,
  onSend,
  setInput,
  inputRef,
  router,
  isRunning,
}: ChatEmptyStateProps) {
  return (
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="mx-auto flex min-h-full w-full max-w-3xl flex-col justify-center px-5 pt-6 pb-[110px] sm:px-8"
          >
            <div className="text-center">
              <p className="text-[11px] font-medium text-[var(--text-muted)]">
                ResearchSwarm
              </p>
              {lastSession ? (
                <>
                  <motion.h2
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className="mt-1.5 text-[28px] font-bold leading-[1.15] tracking-[-0.03em] text-[var(--text-primary)] sm:text-[32px]"
                  >
                    Continue research
                  </motion.h2>
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.05 }}
                    className="mx-auto mt-4 w-full max-w-md"
                  >
                    <button
                      type="button"
                      onClick={() => {
                        setInput(
                          lastSession.prompt ||
                            lastSession.title ||
                            "Compare LangGraph and CrewAI for production systems",
                        );
                        inputRef.current?.focus();
                      }}
                      className="group flex w-full items-center gap-2.5 rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface-hover)_30%,transparent)] px-3.5 py-2.5 text-left transition-all hover:-translate-y-px hover:border-[color-mix(in_srgb,var(--purple)_35%,var(--border))] hover:shadow-[0_8px_24px_rgb(0_0_0/0.14)]"
                    >
                      <span className="h-2 w-2 flex-shrink-0 rounded-full bg-emerald-400/80" />
                      <span className="min-w-0 flex-1 truncate text-sm font-medium text-[var(--text-primary)]">
                        {lastSession.title || lastSession.prompt || "Untitled"}
                      </span>
                      <span className="shrink-0 truncate text-xs text-[var(--text-muted)]">
                        {lastSession.sources_total ?? 0} sources ·{" "}
                        {timeAgo(lastSession.updated_at || lastSession.created_at || "")}
                      </span>
                      <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-[var(--text-secondary)] opacity-0 transition-opacity group-hover:opacity-100">
                        Resume
                        <ArrowUp className="h-3 w-3 -rotate-90" />
                      </span>
                    </button>
                  </motion.div>
                </>
              ) : (
                <>
                  <motion.h2
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className="mt-1.5 text-[42px] font-bold leading-[1.08] tracking-[-0.04em] text-[var(--text-primary)] sm:text-[48px]"
                  >
                    {greeting}, {firstName}
                  </motion.h2>
                  <motion.p
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.05 }}
                    className="mx-auto mt-3 max-w-xl text-sm leading-6 text-[var(--text-muted)]"
                  >
                    One question is enough — the swarm plans, searches, and connects
                    the evidence for you.
                  </motion.p>
                </>
              )}
            </div>

            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.1 }}
              className="mt-6 w-full"
            >
              <Composer variant="hero" {...composerProps} />
              <div className="mt-3 flex flex-wrap justify-center gap-2">
                {suggestions.map(({ label, prompt, icon: Icon, color }) => (
                  <motion.button
                    key={label}
                    type="button"
                    onClick={() => onSend(prompt)}
                    disabled={isRunning}
                    whileHover={{ y: -1 }}
                    whileTap={{ scale: 0.98 }}
                    transition={{ duration: 0.15 }}
                    className={cn(
                      "inline-flex items-center gap-2 rounded-full border border-[color-mix(in_srgb,var(--purple)_18%,var(--border))] bg-[color-mix(in_srgb,var(--surface-hover)_32%,transparent)] px-3 py-1.5 text-xs text-[var(--text-secondary)] transition-colors",
                      "hover:border-[color-mix(in_srgb,var(--purple)_38%,var(--border))] hover:text-[var(--text-primary)] disabled:opacity-50",
                    )}
                  >
                    <span className={`suggestion-icon suggestion-icon-${color} !h-5 !w-5 !rounded-full`}>
                      <Icon className="h-3 w-3" />
                    </span>
                    {label}
                  </motion.button>
                ))}
              </div>
            </motion.div>

            <div className="mt-10">
              <div className="mb-1 flex items-center justify-between">
                <p className="text-[15px] font-semibold tracking-tight text-[var(--text-primary)]">
                  Recent research
                </p>
                <span className="text-xs text-[var(--text-muted)]">
                  From your memory
                </span>
              </div>
              <div className="mt-2">
                {recentItems.length === 0 ? (
                  <p className="rounded-xl px-3 py-2.5 text-sm text-[var(--text-muted)]">
                    No research yet — your sessions will appear here.
                  </p>
                ) : (
                  recentItems.map((run, index) => (
                    <motion.button
                      key={run.key}
                      type="button"
                      onClick={() => {
                        setInput(run.prompt);
                        inputRef.current?.focus();
                      }}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2, delay: index * 0.05 }}
                      whileHover={{ y: -1 }}
                      whileTap={{ scale: 0.995 }}
                      className="group flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-[color-mix(in_srgb,var(--surface-hover)_45%,transparent)] hover:shadow-[0_6px_20px_rgb(0_0_0/0.12)]"
                    >
                      <span
                        className={cn(
                          "h-1.5 w-1.5 flex-shrink-0 rounded-full",
                          run.status === "completed"
                            ? "bg-emerald-400/80"
                            : run.status === "running"
                              ? "animate-pulse bg-amber-400"
                              : run.status === "failed"
                                ? "bg-rose-400/80"
                                : "bg-[var(--text-muted)]",
                        )}
                      />
                      <span className="min-w-0 flex-1 truncate text-sm font-medium text-[var(--text-primary)]">
                        {run.title}
                      </span>
                      <span className="shrink-0 truncate text-xs text-[var(--text-muted)]">
                        {run.meta}
                      </span>
                      <span className="flex shrink-0 items-center gap-1 text-xs text-[var(--text-secondary)] opacity-0 transition-all duration-150 group-hover:-translate-x-0.5 group-hover:opacity-100">
                        Resume
                        <ArrowUp className="h-3 w-3 -rotate-90" />
                      </span>
                    </motion.button>
                  ))
                )}
              </div>
            </div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: 0.05 }}
              className="card-glass mt-8 p-5"
            >
              {recentCollections.length > 0 ? (
                <>
                  <p className="text-[15px] font-semibold tracking-tight text-[var(--text-primary)]">
                    Recent collections
                  </p>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    Organized workspaces from your research
                  </p>
                  <div className="mt-4 space-y-1">
                    {recentCollections.map((collection) => (
                      <button
                        key={collection.id}
                        type="button"
                        onClick={() => {
                          setInput(
                            `Research within the "${collection.name}" collection`,
                          );
                          inputRef.current?.focus();
                        }}
                        className="group flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-[var(--surface-hover)]"
                      >
                        <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg bg-violet-500/10 text-violet-300">
                          <FolderOpen className="h-3.5 w-3.5" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]">
                            {collection.name}
                          </span>
                          {collection.description && (
                            <span className="block truncate text-[10px] text-[var(--text-muted)]">
                              {collection.description}
                            </span>
                          )}
                        </span>
                        <ArrowUp className="h-3 w-3 -rotate-90 text-[var(--text-muted)] opacity-0 transition-opacity group-hover:opacity-100" />
                      </button>
                    ))}
                  </div>
                </>
              ) : reportList.length > 0 ? (
                <>
                  <p className="text-[15px] font-semibold tracking-tight text-[var(--text-primary)]">
                    {readyReports.some((report) => report.is_pinned)
                      ? "Pinned reports"
                      : "Recent reports"}
                  </p>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    Fully cited research, ready to reopen
                  </p>
                  <div className="mt-4 space-y-1">
                    {reportList.map((report) => (
                      <button
                        key={report.id}
                        type="button"
                        onClick={() => router.push(`/app/reports/${report.id}`)}
                        className="group flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-[var(--surface-hover)]"
                      >
                        <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg bg-[var(--accent-violet)]/10 text-[var(--accent-violet)]">
                          <FileCheck2 className="h-3.5 w-3.5" />
                        </span>
                        <span className="min-w-0 flex-1 truncate text-sm text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]">
                          {report.title}
                        </span>
                        <span className="shrink-0 text-[10px] text-[var(--text-muted)]">
                          {timeAgo(report.created_at || "")}
                        </span>
                        <ArrowUp className="h-3 w-3 -rotate-90 text-[var(--text-muted)] opacity-0 transition-opacity group-hover:opacity-100" />
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <>
                  <p className="text-[15px] font-semibold tracking-tight text-[var(--text-primary)]">
                    Capabilities
                  </p>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    Everything the swarm can draw on
                  </p>
                  <div className="mt-4 grid grid-cols-1 gap-1 sm:grid-cols-2">
                    {capabilities.map(({ label, icon: Icon, tint }) => (
                      <div
                        key={label}
                        className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-[var(--text-secondary)]"
                      >
                        <span className={cn("flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg", tint)}>
                          <Icon className="h-3.5 w-3.5" />
                        </span>
                        {label}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </motion.div>
          </motion.section>
  );
}
