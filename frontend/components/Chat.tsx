"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  ArrowUp,
  Bot,
  BrainCircuit,
  Check,
  ChevronRight,
  Copy,
  Eraser,
  FileSearch,
  FileText,
  Gauge,
  Globe2,
  Loader2,
  Paperclip,
  Scale,
  Search,
  Sparkles,
  User,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentLog, Message, UploadedDocument } from "@/lib/types";
import AgentThinkingPanel from "./AgentThinkingPanel";
import StreamingText from "./StreamingText";
import FollowUpSuggestions from "./FollowUpSuggestions";
import ConfidenceRenderer from "./ConfidenceRenderer";
import DebateView from "./DebateView";

interface ChatProps {
  messages: Message[];
  documents: UploadedDocument[];
  onSend: (query: string) => void;
  onAttach: () => void;
  isRunning: boolean;
  debateMode?: boolean;
  onDebateToggle?: () => void;
  streamLogs?: AgentLog[];
  elapsed?: number;
  composerRef?: React.RefObject<HTMLTextAreaElement | null>;
  liveSessions?: LiveSession[];
  liveLastSession?: LiveSession | null;
}

export interface LiveSession {
  id: string;
  title: string;
  prompt: string;
  status: string;
  mode: string;
  sources_total: number;
  created_at: string;
  updated_at: string;
}

function timeAgo(iso: string): string {
  const t = new Date(iso).getTime();
  if (!t) return "";
  const diff = Date.now() - t;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

const suggestions = [
  {
    label: "Compare GPT-5 and Claude",
    prompt:
      "Compare the latest GPT and Claude models across reasoning, coding, context, and price. Cite reliable sources.",
    icon: Sparkles,
    color: "violet",
  },
  {
    label: "Research LangGraph",
    prompt:
      "Research LangGraph. Explain architecture, StateGraph, advantages, and compare with LangChain. Generate a report with citations.",
    icon: BrainCircuit,
    color: "cyan",
  },
  {
    label: "Summarize uploaded PDFs",
    prompt:
      "Summarize the uploaded PDFs, identify the main claims, and highlight disagreements between them.",
    icon: FileSearch,
    color: "emerald",
  },
  {
    label: "Review a GitHub repository",
    prompt:
      "Create a research-backed checklist for reviewing the architecture and engineering quality of a GitHub repository.",
    icon: Search,
    color: "orange",
  },
] as const;

const recentRuns = [
  {
    title: "LangGraph vs CrewAI",
    meta: "21 sources · 2h ago",
  },
  {
    title: "LLM alignment 2025",
    meta: "18 sources · yesterday",
  },
  {
    title: "Postgres vs MongoDB",
    meta: "14 sources · Monday",
  },
] as const;

const capabilityCards = [
  {
    icon: Globe2,
    title: "Web research",
    detail: "Real-time search",
    meta: "Live",
    chips: ["DuckDuckGo", "Bing", "Serper"],
    color: "cyan",
  },
  {
    icon: FileText,
    title: "PDF RAG",
    detail: "Local document retrieval",
    meta: "20 files · 4 indexed",
    chips: ["PyMuPDF", "nomic-embed"],
    color: "emerald",
  },
  {
    icon: BrainCircuit,
    title: "Multi-agent",
    detail: "Plan · Research · Answer",
    meta: "4 agents",
    chips: ["LangGraph", "Ollama"],
    color: "violet",
  },
] as const;

const researchModes = [
  { label: "Quick search", directive: "Quick search:", hint: "Fast answer, fewer sources" },
  { label: "Deep research", directive: "Deep research:", hint: "Plan, search 18+ sources, rank evidence" },
  { label: "Compare", directive: "Compare:", hint: "Trade-offs across candidates" },
  { label: "Summarize", directive: "Summarize:", hint: "Condense documents or topics" },
  { label: "Verify", directive: "Verify:", hint: "Check claims against sources" },
] as const;

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="message-action"
      aria-label={copied ? "Answer copied" : "Copy answer"}
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-emerald-400" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function ChatMessage({ message, isLatest }: { message: Message; isLatest: boolean }) {
  const isUser = message.role === "user";
  const isThinking =
    message.content === "..." || message.content === "Thinking...";

  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "mb-8 flex gap-3 sm:gap-4",
        isUser && "flex-row-reverse",
      )}
    >
      <div
        className={cn(
          "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl border",
          isUser
            ? "border-blue-400/20 bg-blue-500/10 text-blue-300"
            : "border-violet-400/20 bg-violet-500/10 text-violet-300",
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      <div
        className={cn(
          "group min-w-0",
          isUser ? "max-w-[85%] sm:max-w-[72%]" : "max-w-[92%] sm:max-w-[86%]",
        )}
      >
        <div
          className={cn(
            "rounded-2xl px-4 py-3.5 sm:px-5 sm:py-4",
            isUser
              ? "border border-blue-400/15 bg-blue-500/[0.07]"
              : "answer-surface",
          )}
        >
          {isThinking ? (
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2.5">
                <span className="relative flex h-5 w-5 items-center justify-center">
                  <span className="absolute inset-0 animate-ping rounded-full bg-violet-400/15" />
                  <Loader2 className="relative h-4 w-4 animate-spin text-violet-300" />
                </span>
                <span className="text-sm text-[var(--text-secondary)]">
                  Coordinating the research swarm...
                </span>
              </div>
            </div>
          ) : isUser ? (
            <div className="prose-custom prose-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          ) : isLatest ? (
            <StreamingText
              content={message.content}
              speed={12}
            />
          ) : (
            <div className="prose-custom prose-sm">
              <ConfidenceRenderer content={message.content} />
            </div>
          )}
        </div>

        {!isUser && !isThinking && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <CopyButton text={message.content} />
            <span className="message-action">
              <FileSearch className="h-3.5 w-3.5" />
              {message.sources?.length || 0} sources
            </span>
            <span className="message-action">
              <Gauge className="h-3.5 w-3.5" />
              Metrics
            </span>
            {message.answerMode && message.answerMode !== "normal" && (
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[9px] font-medium",
                  message.answerMode === "fallback"
                    ? "bg-amber-500/10 text-amber-400"
                    : "bg-rose-500/10 text-rose-400",
                )}
              >
                <AlertTriangle className="h-3 w-3" />
                {message.answerMode === "fallback" ? "Fallback" : "No evidence"}
              </span>
            )}
            <span className="ml-auto hidden text-[10px] text-[var(--text-muted)] sm:block">
              Generated by ResearchSwarm
            </span>
          </div>
        )}
        {!isUser && !isThinking && message.debate && (
          <div className="mt-4">
            <DebateView debate={message.debate} />
          </div>
        )}
      </div>
    </motion.article>
  );
}

export default function Chat({
  messages,
  documents,
  onSend,
  onAttach,
  isRunning,
  debateMode = false,
  onDebateToggle,
  streamLogs = [],
  elapsed = 0,
  composerRef,
  liveSessions,
  liveLastSession,
}: ChatProps) {
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<(typeof researchModes)[number] | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = composerRef || useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamLogs]);

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

  const recentItems: Array<{
    key: string;
    title: string;
    meta: string;
    prompt: string;
  }> = (liveSessions && liveSessions.length > 0
    ? liveSessions
        .filter((s) => s.id !== liveLastSession?.id)
        .slice(0, 3)
        .map((s) => ({
          key: s.id,
          title: s.title || s.prompt,
          meta: `${s.sources_total ?? 0} sources · ${timeAgo(s.updated_at || s.created_at || "")}`,
          prompt: s.prompt,
        }))
    : recentRuns.map((r) => ({
        key: r.title,
        title: r.title,
        meta: r.meta,
        prompt: r.title,
      }))
  ).slice(0, 3);

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mx-auto flex min-h-full w-full max-w-4xl flex-col justify-center px-5 py-10 sm:px-8 lg:py-12"
          >
            <div className="mb-8">
              <span className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-500/10 text-violet-300 shadow-lg shadow-violet-950/20">
                <Sparkles className="h-5 w-5" />
              </span>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-violet-300">
                Today&apos;s workspace
              </p>
              <h2 className="mt-2 text-balance text-3xl font-semibold tracking-[-0.035em] text-[var(--text-primary)] sm:text-4xl">
                What do you want to research today?
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--text-muted)]">
                Start with a question, add your documents, and watch specialized
                agents gather and connect the evidence.
              </p>
            </div>

            <div className="continue-card">
              <div className="flex items-center justify-between">
                <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
                  Continue last run
                </p>
                <span className="ready-badge">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      liveLastSession?.status === "completed" ||
                      !liveLastSession?.status
                        ? "bg-emerald-400"
                        : "bg-amber-400"
                    }`}
                  />
                  {liveLastSession
                    ? liveLastSession.status
                        .replace(/_/g, " ")
                        .replace(/^\w/, (c) => c.toUpperCase())
                    : "Completed"}
                </span>
              </div>
              <p className="mt-2.5 text-sm font-medium text-[var(--text-primary)]">
                {liveLastSession?.title || liveLastSession?.prompt ||
                  "Compare LangGraph and CrewAI for production systems"}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-[var(--text-muted)]">
                <span className="flex items-center gap-1.5">
                  <Check className="h-3 w-3 text-emerald-400" />
                  {liveLastSession?.sources_total ?? 21} sources
                </span>
                {liveLastSession?.mode && (
                  <span className="flex items-center gap-1.5">
                    <Check className="h-3 w-3 text-emerald-400" />
                    {liveLastSession.mode.replace(/_/g, " ")}
                  </span>
                )}
                {!liveLastSession?.mode && (
                  <span className="flex items-center gap-1.5">
                    <Check className="h-3 w-3 text-emerald-400" />
                    7 citations
                  </span>
                )}
                {liveLastSession?.updated_at && (
                  <span className="flex items-center gap-1.5">
                    <Check className="h-3 w-3 text-emerald-400" />
                    {timeAgo(liveLastSession.updated_at)}
                  </span>
                )}
                {!liveLastSession?.updated_at && (
                  <span className="flex items-center gap-1.5">
                    <Check className="h-3 w-3 text-emerald-400" />
                    6.4s execution
                  </span>
                )}
                <span className="ml-auto hidden font-mono text-[9px] sm:inline">
                  {liveLastSession
                    ? liveLastSession.updated_at
                      ? timeAgo(liveLastSession.updated_at)
                      : "just now"
                    : "2h ago"}
                </span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setInput(
                    liveLastSession?.prompt ||
                      liveLastSession?.title ||
                      "Compare LangGraph and CrewAI for production systems",
                  );
                  inputRef.current?.focus();
                }}
                className="continue-button"
              >
                Resume this run
                <ArrowUp className="h-3 w-3 -rotate-90" />
              </button>
            </div>

            <div className="mt-6">
              <div className="mb-2.5 flex items-center justify-between">
                <p className="text-[10px] font-medium text-[var(--text-secondary)]">
                  Recent research
                </p>
                <span className="text-[9px] text-[var(--text-muted)]">
                  From your memory
                </span>
              </div>
              <div className="grid gap-1.5 sm:grid-cols-3">
                {recentItems.map((run) => (
                  <button
                    key={run.key}
                    type="button"
                    onClick={() => {
                      setInput(run.prompt);
                      inputRef.current?.focus();
                    }}
                    className="run-row"
                  >
                    <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-400/10 text-emerald-300">
                      <Check className="h-3 w-3" />
                    </span>
                    <span className="min-w-0 flex-1 text-left">
                      <span className="block truncate text-[11px] font-medium text-[var(--text-secondary)]">
                        {run.title}
                      </span>
                      <span className="block text-[9px] text-[var(--text-muted)]">
                        {run.meta}
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-7">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-xs font-medium text-[var(--text-secondary)]">
                  Suggested prompts
                </p>
                <span className="text-[10px] text-[var(--text-muted)]">
                  Choose one to begin
                </span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {suggestions.map(({ label, prompt, icon: Icon, color }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => onSend(prompt)}
                    disabled={isRunning}
                    className="suggestion-card group"
                  >
                    <span className={`suggestion-icon suggestion-icon-${color}`}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="flex-1 text-left text-sm text-[var(--text-secondary)] transition-colors group-hover:text-[var(--text-primary)]">
                      {label}
                    </span>
                    <ChevronRight className="h-3.5 w-3.5 text-[var(--text-muted)] transition-transform group-hover:translate-x-0.5" />
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-7 grid gap-2 sm:grid-cols-3">
              {capabilityCards.map(
                ({ icon: Icon, title, detail, meta, chips, color }) => (
                  <article key={title} className="capability-card">
                    <div className="flex items-start justify-between">
                      <span className={`capability-icon capability-icon-${color}`}>
                        <Icon className="h-4 w-4" />
                      </span>
                      <span className="ready-badge">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                        {meta}
                      </span>
                    </div>
                    <p className="mt-4 text-sm font-medium text-[var(--text-primary)]">
                      {title}
                    </p>
                    <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                      {detail}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-1">
                      {chips.map((chip) => (
                        <span key={chip} className="capability-chip">
                          <Check className="h-2 w-2 text-emerald-400" />
                          {chip}
                        </span>
                      ))}
                    </div>
                  </article>
                ),
              )}
            </div>

            {documents.length > 0 && (
              <div className="mt-6 flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.025] p-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-300">
                  <FileText className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-xs font-medium text-[var(--text-primary)]">
                    {documents.length} recent document
                    {documents.length === 1 ? "" : "s"}
                  </p>
                  <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">
                    Ready to include in your next research task
                  </p>
                </div>
              </div>
            )}
          </motion.section>
        ) : (
          <section
            className="mx-auto w-full max-w-4xl px-5 py-8 sm:px-8"
            role="log"
            aria-live="polite"
            aria-label="Research conversation"
          >
            <AnimatePresence initial={false}>
              {messages.map((message, i) => (
                <ChatMessage
                  key={message.id}
                  message={message}
                  isLatest={i === messages.length - 1 && !isRunning}
                />
              ))}
            </AnimatePresence>
            {isRunning && streamLogs.length > 0 && (
              <AgentThinkingPanel
                logs={streamLogs}
                isRunning={isRunning}
                elapsed={elapsed}
              />
            )}
            {!isRunning && (() => {
              const lastMsg = [...messages].reverse().find(
                (m) => m.role === "assistant" && m.content !== "Thinking..." && m.content !== "..."
              );
              return lastMsg ? (
                <FollowUpSuggestions
                  answer={lastMsg.content}
                  onSelect={onSend}
                />
              ) : null;
            })()}
            <div ref={endRef} />
          </section>
        )}
      </div>

      <div className="composer-wrap">
        <div className="mx-auto mb-2 flex w-full max-w-4xl items-center gap-1.5 overflow-x-auto pb-0.5">
          {researchModes.map((m) => (
            <button
              key={m.label}
              type="button"
              onClick={() => setMode(mode?.label === m.label ? null : m)}
              className={cn(
                "mode-chip",
                mode?.label === m.label && "mode-chip-active",
              )}
              title={m.hint}
            >
              {m.label}
            </button>
          ))}
          {mode && (
            <span className="ml-auto hidden shrink-0 text-[9px] text-[var(--text-muted)] sm:block">
              {mode.hint}
            </span>
          )}
        </div>

        <form
          onSubmit={handleSubmit}
          className="composer mx-auto w-full max-w-4xl"
        >
          <textarea
            id="research-composer"
            ref={inputRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              mode
                ? `${mode.label} — ${mode.hint}. ResearchSwarm will build a plan...`
                : "Ask anything. ResearchSwarm will build a plan..."
            }
            className="min-h-[54px] w-full resize-none bg-transparent px-4 pb-2 pt-4 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
            rows={1}
            disabled={isRunning}
            aria-label="Research question"
          />
          <div className="flex items-center justify-between gap-3 border-t border-white/[0.05] px-2.5 py-2">
            <div className="flex min-w-0 items-center gap-1">
              <button
                type="button"
                onClick={onAttach}
                className="composer-tool"
              >
                <Paperclip className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Attach</span>
              </button>
              <button
                type="button"
                onClick={onDebateToggle}
                className={cn(
                  "composer-tool",
                  debateMode && "text-violet-400"
                )}
                aria-label={debateMode ? "Disable debate mode" : "Enable debate mode"}
              >
                <Scale className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Debate</span>
                {debateMode && (
                  <span className="ml-0.5 h-1.5 w-1.5 rounded-full bg-violet-400" />
                )}
              </button>
              {mode && (
                <span className="composer-tool text-violet-300">
                  <Sparkles className="h-3 w-3" />
                  {mode.label}
                </span>
              )}
              <span className="composer-tool hidden sm:flex">
                <Globe2 className="h-3.5 w-3.5 text-cyan-400" />
                Web
              </span>
            </div>

            <div className="flex items-center gap-2">
              {input && (
                <button
                  type="button"
                  onClick={() => {
                    setInput("");
                    inputRef.current?.focus();
                  }}
                  className="icon-button h-8 w-8"
                  aria-label="Clear question"
                >
                  <Eraser className="h-3.5 w-3.5" />
                </button>
              )}
              <button
                type="submit"
                disabled={!input.trim() || isRunning}
                className="composer-submit"
                aria-label={isRunning ? "Research in progress" : "Start research"}
              >
                {isRunning ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowUp className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>
        </form>
        <p className="mt-2 text-center text-[10px] text-[var(--text-muted)]">
          Enter to send · Shift + Enter for a new line · Research can make mistakes
        </p>
      </div>
    </div>
  );
}
