"use client";

import { memo, useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  Bot,
  Check,
  Copy,
  FileSearch,
  Gauge,
  Loader2,
  Sparkles,
  User,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { Message } from "@/lib/types";
import StreamingText from "@/components/StreamingText";
import ConfidenceRenderer from "@/components/ConfidenceRenderer";
import DebateView from "@/components/DebateView";

export function SessionDivider({ timestamp }: { timestamp: number }) {
  const date = new Date(timestamp);
  const time = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const isToday = new Date().toDateString() === date.toDateString();
  const label = isToday
    ? `New research · ${time}`
    : `New research · ${date.toLocaleDateString([], { month: "short", day: "numeric" })} · ${time}`;

  return (
    <div
      role="separator"
      aria-label={label}
      className="mb-8 flex items-center gap-3"
    >
      <span className="h-px flex-1 bg-gradient-to-r from-transparent to-[color-mix(in_srgb,var(--border)_70%,transparent)]" />
      <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1 text-[9px] font-medium uppercase tracking-[0.1em] text-[var(--text-muted)]">
        <Sparkles className="h-2.5 w-2.5 text-violet-400" />
        {label}
      </span>
      <span className="h-px flex-1 bg-gradient-to-l from-transparent to-[color-mix(in_srgb,var(--border)_70%,transparent)]" />
    </div>
  );
}

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

// Memoized: a message's rendered output depends only on its own content, so

export const ChatMessage = memo(function ChatMessage({
  message,
  isLatest,
}: {
  message: Message;
  isLatest: boolean;
}) {
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
});
