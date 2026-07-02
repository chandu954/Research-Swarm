"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
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

interface ChatProps {
  messages: Message[];
  documents: UploadedDocument[];
  onSend: (query: string) => void;
  onAttach: () => void;
  isRunning: boolean;
  streamLogs?: AgentLog[];
  elapsed?: number;
  composerRef?: React.RefObject<HTMLTextAreaElement | null>;
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

const capabilityCards = [
  {
    icon: Globe2,
    title: "Web research",
    detail: "Real-time search",
    meta: "Ready",
    color: "cyan",
  },
  {
    icon: FileText,
    title: "PDF RAG",
    detail: "Local document retrieval",
    meta: "20+ files",
    color: "emerald",
  },
  {
    icon: BrainCircuit,
    title: "Multi-agent",
    detail: "Plan · Research · Answer",
    meta: "4 agents",
    color: "violet",
  },
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
            <span className="ml-auto hidden text-[10px] text-[var(--text-muted)] sm:block">
              Generated by ResearchSwarm
            </span>
          </div>
        )}
      </div>
    </motion.article>
  );
}

function ThinkingMessage({ content }: { content: string }) {
  const [displayed, setDisplayed] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDisplayed(true), 100);
    return () => clearTimeout(timer);
  }, []);

  if (!displayed) return null;

  return (
    <div className="prose-custom prose-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

export default function Chat({
  messages,
  documents,
  onSend,
  onAttach,
  isRunning,
  streamLogs = [],
  elapsed = 0,
  composerRef,
}: ChatProps) {
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = composerRef || useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamLogs]);

  const submitQuery = () => {
    const query = input.trim();
    if (!query || isRunning) return;
    onSend(query);
    setInput("");
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitQuery();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitQuery();
    }
  };

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
                ResearchSwarm AI
              </p>
              <h2 className="mt-2 text-balance text-3xl font-semibold tracking-[-0.035em] text-[var(--text-primary)] sm:text-4xl">
                What do you want to research today?
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--text-muted)]">
                Start with a question, add your documents, and watch specialized
                agents gather and connect the evidence.
              </p>
            </div>

            <div>
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
                ({ icon: Icon, title, detail, meta, color }) => (
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
            placeholder="Ask anything. ResearchSwarm will build a plan..."
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
