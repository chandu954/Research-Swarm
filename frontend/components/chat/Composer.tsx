"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowUp,
  BrainCircuit,
  Eraser,
  Github,
  Globe2,
  Loader2,
  Paperclip,
  Scale,
  Sparkles,
  Square,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { researchModes, type ResearchMode } from "@/lib/chat-presets";

export interface ComposerProps {
  variant: "hero" | "bar";
  input: string;
  setInput: (value: string) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onAttach: () => void;
  onCancel?: () => void;
  onDebateToggle?: () => void;
  debateMode?: boolean;
  isRunning: boolean;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  mode: ResearchMode | null;
  setMode: (mode: ResearchMode | null) => void;
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

export function Composer({
  variant,
  input,
  setInput,
  onSubmit,
  onKeyDown,
  onAttach,
  onCancel,
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
          {isRunning && onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className={cn(
                "inline-flex items-center justify-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium text-[var(--text-secondary)] transition-colors",
                "border border-white/[0.08] hover:border-rose-400/40 hover:text-rose-300",
              )}
              aria-label="Cancel research"
            >
              <Square className="h-3 w-3 fill-current" />
              Cancel
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
