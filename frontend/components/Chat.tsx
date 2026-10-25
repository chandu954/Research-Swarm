"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence } from "framer-motion";
import { AlertTriangle, ChevronDown, RotateCcw } from "lucide-react";

import { useAuth } from "@/lib/auth";
import type { AgentLog, Message, UploadedDocument } from "@/lib/types";
import type { LiveCollection, LiveReport, LiveSession } from "@/lib/supabase/query";
import {
  rotatingPlaceholders,
  timeAgo,
  type ResearchMode,
} from "@/lib/chat-presets";
import AgentThinkingPanel from "./AgentThinkingPanel";
import FollowUpSuggestions from "./FollowUpSuggestions";
import ChatEmptyState, { type RecentItem } from "./chat/ChatEmptyState";
import { ChatMessage, SessionDivider } from "./chat/ChatMessage";
import { Composer, type ComposerProps } from "./chat/Composer";

export type { LiveSession } from "@/lib/supabase/query";

interface ChatProps {
  messages: Message[];
  documents: UploadedDocument[];
  onSend: (query: string) => void;
  onAttach: () => void;
  onCancel?: () => void;
  isRunning: boolean;
  debateMode?: boolean;
  onDebateToggle?: () => void;
  streamLogs?: AgentLog[];
  composerRef?: React.RefObject<HTMLTextAreaElement | null>;
  liveSessions?: LiveSession[];
  liveLastSession?: LiveSession | null;
  collections?: LiveCollection[];
  reports?: LiveReport[];
  runError?: string | null;
  onRetry?: () => void;
}

export default function Chat({
  messages,
  documents,
  onSend,
  onAttach,
  onCancel,
  isRunning,
  debateMode = false,
  onDebateToggle,
  streamLogs = [],
  composerRef,
  liveSessions,
  liveLastSession,
  collections = [],
  reports = [],
  runError = null,
  onRetry,
}: ChatProps) {
  const { user } = useAuth();
  const router = useRouter();
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<ResearchMode | null>(null);
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const localInputRef = useRef<HTMLTextAreaElement>(null);
  const inputRef = composerRef || localInputRef;
  const [isNearBottom, setIsNearBottom] = useState(true);
  const jumpedAtRef = useRef(0);

  // Follow new content only while the user is pinned to the bottom; once they
  // scroll up, stop pulling the viewport away from what they are reading.
  const handleScroll = () => {
    if (performance.now() - jumpedAtRef.current < 400) return;
    const el = scrollRef.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 160;
    setIsNearBottom((prev) => (prev === near ? prev : near));
  };

  useEffect(() => {
    if (!isNearBottom) return;
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamLogs, isNearBottom]);

  const jumpToLatest = () => {
    jumpedAtRef.current = performance.now();
    setIsNearBottom(true);
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (mode || isRunning || messages.length > 0 || input.length > 0) return;
    const id = setInterval(() => {
      setPlaceholderIdx((i) => (i + 1) % rotatingPlaceholders.length);
    }, 5000);
    return () => clearInterval(id);
  }, [mode, isRunning, messages.length, input]);

  const submitQuery = () => {
    const query = input.trim();
    if (!query || isRunning) return;
    onSend(mode ? `${mode.directive} ${query}` : query);
    setInput("");
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitQuery();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !isRunning) {
      event.preventDefault();
      submitQuery();
    }
  };

  const recentItems: RecentItem[] = (liveSessions && liveSessions.length > 0
    ? liveSessions
        .filter((session) => session.id !== liveLastSession?.id)
        .slice(0, 3)
        .map((session) => ({
          key: session.id,
          title: session.title || session.prompt,
          meta: `${session.sources_total ?? 0} sources · ${timeAgo(
            session.updated_at || session.created_at || "",
          )}`,
          prompt: session.prompt,
          status: session.status,
        }))
    : []
  ).slice(0, 3);

  const recentCollections = collections.slice(0, 4);
  const readyReports = reports.filter((report) => report.status === "ready");
  const reportList = (
    readyReports.some((report) => report.is_pinned)
      ? readyReports.filter((report) => report.is_pinned)
      : readyReports
  ).slice(0, 4);

  const hour = new Date().getHours();
  const greeting =
    hour < 5
      ? "Good night"
      : hour < 12
        ? "Good morning"
        : hour < 18
          ? "Good afternoon"
          : "Good evening";
  const firstName = user?.name?.split(" ")[0] || "there";

  const attachHint =
    documents.length > 0
      ? `${documents.length} document${documents.length === 1 ? "" : "s"} ready`
      : "Attach PDFs to include";

  const lastSession = liveLastSession ?? null;
  const placeholder = mode
    ? `${mode.label} — ${mode.hint}. ResearchSwarm will build a plan...`
    : rotatingPlaceholders[placeholderIdx % rotatingPlaceholders.length];

  const composerProps: Omit<ComposerProps, "variant"> = {
    input,
    setInput,
    onSubmit: handleSubmit,
    onKeyDown: handleKeyDown,
    onAttach,
    onCancel,
    onDebateToggle,
    debateMode,
    isRunning,
    inputRef,
    mode,
    setMode,
    attachHint,
    placeholder,
  };

  return (
    <div className="flex h-full flex-col">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="relative min-h-0 flex-1 overflow-y-auto"
      >
        {messages.length === 0 ? (
          <ChatEmptyState
            lastSession={lastSession}
            greeting={greeting}
            firstName={firstName}
            recentItems={recentItems}
            recentCollections={recentCollections}
            reportList={reportList}
            readyReports={readyReports}
            composerProps={composerProps}
            onSend={onSend}
            setInput={setInput}
            inputRef={inputRef}
            router={router}
            isRunning={isRunning}
          />
        ) : (
          <section
            className="mx-auto w-full max-w-4xl px-5 py-8 sm:px-8"
            role="log"
            aria-live="polite"
            aria-label="Research conversation"
          >
            <AnimatePresence initial={false}>
              {messages.map((message, i) => (
                <Fragment key={message.id}>
                  {message.role === "user" && i > 0 && (
                    <SessionDivider timestamp={message.timestamp} />
                  )}
                  <ChatMessage
                    message={message}
                    isLatest={i === messages.length - 1 && !isRunning}
                  />
                </Fragment>
              ))}
            </AnimatePresence>
            {isRunning && streamLogs.length > 0 && (
              <AgentThinkingPanel logs={streamLogs} isRunning={isRunning} />
            )}
            {!isRunning && runError && (
              <div
                role="alert"
                className="mb-6 flex items-start gap-3 rounded-xl border border-rose-400/20 bg-rose-500/[0.06] px-4 py-3"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-rose-400" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-rose-300">
                    Research failed
                  </p>
                  <p className="mt-0.5 text-xs leading-5 text-[var(--text-muted)]">
                    {runError}
                  </p>
                </div>
                {onRetry && (
                  <button
                    type="button"
                    onClick={onRetry}
                    className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-lg border border-rose-400/25 bg-rose-500/10 px-2.5 py-1.5 text-[11px] font-medium text-rose-300 transition-colors hover:border-rose-400/40 hover:bg-rose-500/15"
                  >
                    <RotateCcw className="h-3 w-3" />
                    Retry research
                  </button>
                )}
              </div>
            )}
            {!isRunning &&
              (() => {
                const lastMsg = [...messages]
                  .reverse()
                  .find(
                    (message) =>
                      message.role === "assistant" &&
                      message.content !== "Thinking..." &&
                      message.content !== "...",
                  );
                return lastMsg ? (
                  <FollowUpSuggestions answer={lastMsg.content} onSelect={onSend} />
                ) : null;
              })()}
            <div ref={endRef} />
          </section>
        )}

        {!isNearBottom && messages.length > 0 && (
          <button
            type="button"
            onClick={jumpToLatest}
            className="absolute bottom-4 left-1/2 z-20 -translate-x-1/2 rounded-full border border-[var(--border-strong)] bg-[var(--surface-elevated)] px-3 py-1.5 text-[10px] font-medium text-[var(--text-secondary)] shadow-lg transition-colors hover:border-[var(--accent-violet)]/40 hover:text-[var(--text-primary)]"
          >
            <ChevronDown className="mr-1 inline h-3 w-3" />
            Jump to latest
          </button>
        )}
      </div>

      {messages.length === 0 ? null : (
        <div className="composer-wrap">
          <Composer variant="bar" {...composerProps} />
        </div>
      )}
    </div>
  );
}
