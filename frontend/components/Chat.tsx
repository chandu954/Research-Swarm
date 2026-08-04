"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  ArrowUp,
  Bot,
  BrainCircuit,
  Check,
  Copy,
  Eraser,
  FileCheck2,
  FileSearch,
  FileText,
  FolderOpen,
  Gauge,
  Github,
  Globe2,
  Loader2,
  Paperclip,
  Scale,
  Search,
  Sparkles,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import type { AgentLog, Message, UploadedDocument } from "@/lib/types";
import type { LiveCollection, LiveReport } from "@/lib/supabase/query";
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
  collections?: LiveCollection[];
  reports?: LiveReport[];
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

const researchModes = [
  { label: "Deep Research", directive: "Deep research:", hint: "Plan, search many sources, rank evidence", icon: Sparkles },
  { label: "Compare", directive: "Compare:", hint: "Trade-offs across candidates", icon: Scale },
  { label: "Think Longer", directive: "Think longer:", hint: "Extra depth per source", icon: BrainCircuit },
  { label: "GitHub", directive: "GitHub:", hint: "Focus on repositories", icon: Github },
] as const;

const capabilities = [
  { label: "Web search", icon: Globe2, tint: "bg-cyan-400/10 text-cyan-400" },
  { label: "PDF analysis", icon: FileText, tint: "bg-emerald-400/10 text-emerald-400" },
  { label: "GitHub research", icon: Github, tint: "bg-orange-400/10 text-orange-400" },
  { label: "Local files", icon: FolderOpen, tint: "bg-amber-400/10 text-amber-400" },
  { label: "Multi-agent planning", icon: BrainCircuit, tint: "bg-violet-400/10 text-violet-400" },
  { label: "Cited reports", icon: FileCheck2, tint: "bg-blue-400/10 text-blue-400" },
] as const;

const rotatingPlaceholders = [
  "Compare GPT-5 vs Claude",
  "Analyze uploaded PDFs",
  "Review a GitHub repository",
  "Research LangGraph",
  "Find AI startup competitors",
  "Generate a literature review",
  "Track the latest AI agent frameworks",
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

interface ComposerProps {
  variant: "hero" | "bar";
  input: string;
  setInput: (value: string) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onAttach: () => void;
  onDebateToggle?: () => void;
  debateMode?: boolean;
  isRunning: boolean;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  mode: (typeof researchModes)[number] | null;
  setMode: (mode: (typeof researchModes)[number] | null) => void;
  attachHint?: string;
  placeholder: string;
}

function GroupLabel({ children }: { children: string }) {
  return (
    <span className="mr-1 hidden text-[8px] font-medium uppercase tracking-[0.1em] text-[color-mix(in_srgb,var(--text-muted)_70%,transparent)] lg:inline">
      {children}
    </span>
  );
}

function Composer({
  variant,
  input,
  setInput,
  onSubmit,
  onKeyDown,
  onAttach,
  onDebateToggle,
  debateMode = false,
  isRunning,
  inputRef,
  mode,
  setMode,
  attachHint,
  placeholder,
}: ComposerProps) {
  const isHero = variant === "hero";

  const actionClass = (active = false) =>
    cn(
      "inline-flex items-center justify-center gap-1.5 rounded-lg px-2 py-1 text-[11px] transition-colors duration-150",
      active
        ? "bg-violet-500/12 text-violet-300"
        : "text-[var(--text-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-secondary)]",
    );

  return (
    <form
      onSubmit={onSubmit}
      className={cn("composer", isHero ? "composer-hero" : "mx-auto w-full max-w-4xl")}
    >
      <div className="relative">
        <textarea
          id="research-composer"
          ref={inputRef}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={onKeyDown}
          className={cn(
            "w-full resize-none bg-transparent text-[var(--text-primary)] caret-[#a78bfa] outline-none placeholder:text-[color-mix(in_srgb,var(--text-secondary)_68%,transparent)]",
            isHero
              ? "min-h-[72px] px-5 pb-1.5 pt-3.5 text-[15px]"
              : "min-h-[46px] px-4 pb-1 pt-3 text-sm",
          )}
          rows={isHero ? 1 : 1}
          disabled={isRunning}
          aria-label="Research question"
        />
        {!input && !isRunning && (
          <AnimatePresence mode="wait">
            <motion.span
              key={placeholder}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.18 }}
              className={cn(
                "pointer-events-none absolute text-[color-mix(in_srgb,var(--text-secondary)_68%,transparent)]",
                isHero ? "left-5 top-3.5 text-[15px]" : "left-4 top-3 text-sm",
              )}
            >
              {placeholder}
            </motion.span>
          </AnimatePresence>
        )}
      </div>
      <div className="flex items-center gap-2.5 border-t border-white/[0.05] px-3 py-1.5">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-1">
          <div className="flex items-center">
            <GroupLabel>Files</GroupLabel>
            <button
              type="button"
              onClick={onAttach}
              className={actionClass()}
              title={attachHint}
              aria-label={attachHint || "Attach documents"}
            >
              <Paperclip className="h-3.5 w-3.5" />
              <span>Attach</span>
            </button>
          </div>

          <div className="flex items-center border-l border-white/[0.05] pl-4">
            <GroupLabel>Research</GroupLabel>
            <span className={cn(actionClass(), "cursor-default")}>
              <Globe2 className="h-3.5 w-3.5 text-cyan-400" />
              <span>Web</span>
            </span>
            <button
              type="button"
              onClick={() => setMode(mode?.label === "Deep Research" ? null : researchModes[0])}
              className={actionClass(mode?.label === "Deep Research")}
              title={researchModes[0].hint}
              aria-pressed={mode?.label === "Deep Research"}
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Deep</span>
            </button>
            <button
              type="button"
              onClick={() => setMode(mode?.label === "Compare" ? null : researchModes[1])}
              className={actionClass(mode?.label === "Compare")}
              title={researchModes[1].hint}
              aria-pressed={mode?.label === "Compare"}
            >
              <Scale className="h-3.5 w-3.5" />
              <span>Compare</span>
            </button>
          </div>

          <div className="flex items-center border-l border-white/[0.05] pl-4">
            <GroupLabel>Models</GroupLabel>
            <button
              type="button"
              onClick={() => setMode(mode?.label === "Think Longer" ? null : researchModes[2])}
              className={actionClass(mode?.label === "Think Longer")}
              title={researchModes[2].hint}
              aria-pressed={mode?.label === "Think Longer"}
            >
              <BrainCircuit className="h-3.5 w-3.5" />
              <span>Think Longer</span>
            </button>
            <button
              type="button"
              onClick={() => setMode(mode?.label === "GitHub" ? null : researchModes[3])}
              className={actionClass(mode?.label === "GitHub")}
              title={researchModes[3].hint}
              aria-pressed={mode?.label === "GitHub"}
            >
              <Github className="h-3.5 w-3.5" />
              <span>GitHub</span>
            </button>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {input && (
            <button
              type="button"
              onClick={() => {
                setInput("");
                inputRef.current?.focus();
              }}
              className={actionClass()}
              aria-label="Clear question"
            >
              <Eraser className="h-3.5 w-3.5" />
            </button>
          )}
          {onDebateToggle && (
            <button
              type="button"
              onClick={onDebateToggle}
              className={cn(actionClass(), debateMode && "bg-violet-500/12 text-violet-300")}
              title={debateMode ? "Disable debate mode" : "Enable debate mode"}
              aria-label={debateMode ? "Disable debate mode" : "Enable debate mode"}
              aria-pressed={debateMode}
            >
              <Scale className="h-3.5 w-3.5" />
              {debateMode && (
                <span className="ml-0.5 h-1.5 w-1.5 rounded-full bg-violet-400" />
              )}
            </button>
          )}
          <button
            type="submit"
            disabled={!input.trim() || isRunning}
            className={cn("composer-submit", isHero && "h-8 w-8")}
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
  collections = [],
  reports = [],
}: ChatProps) {
  const { user } = useAuth();
  const router = useRouter();
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<(typeof researchModes)[number] | null>(null);
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = composerRef || useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamLogs]);

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

  const recentItems: Array<{
    key: string;
    title: string;
    meta: string;
    prompt: string;
    status: string;
  }> = (liveSessions && liveSessions.length > 0
    ? liveSessions
        .filter((s) => s.id !== liveLastSession?.id)
        .slice(0, 3)
        .map((s) => ({
          key: s.id,
          title: s.title || s.prompt,
          meta: `${s.sources_total ?? 0} sources · ${timeAgo(s.updated_at || s.created_at || "")}`,
          prompt: s.prompt,
          status: s.status,
        }))
    : recentRuns.map((r) => ({
        key: r.title,
        title: r.title,
        meta: r.meta,
        prompt: r.title,
        status: "completed",
      }))
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
    hour < 5 ? "Good night" : hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const firstName = user?.name?.split(" ")[0] || "there";

  const attachHint =
    documents.length > 0
      ? `${documents.length} document${documents.length === 1 ? "" : "s"} ready`
      : "Attach PDFs to include";

  const lastSession = liveLastSession;
  const placeholder = mode
    ? `${mode.label} — ${mode.hint}. ResearchSwarm will build a plan...`
    : rotatingPlaceholders[placeholderIdx % rotatingPlaceholders.length];

  const composerProps = {
    input,
    setInput,
    onSubmit: handleSubmit,
    onKeyDown: handleKeyDown,
    onAttach,
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
      <div className="min-h-0 flex-1 overflow-y-auto">
        {messages.length === 0 ? (
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
                {recentItems.map((run, index) => (
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
                ))}
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

      {messages.length === 0 ? null : (
        <div className="composer-wrap">
          <Composer variant="bar" {...composerProps} />
        </div>
      )}
    </div>
  );
}
