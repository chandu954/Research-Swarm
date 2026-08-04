"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  Check,
  FileText,
  Globe2,
  ListChecks,
  Pin,
  RefreshCw,
  Star,
} from "lucide-react";

const QUESTION = "How does LangGraph compare to CrewAI for production systems?";

const STAGES = [
  { icon: ListChecks, label: "Planning", detail: "3 agents · 2 steps", color: "violet" },
  { icon: Globe2, label: "Searching sources", detail: "21 sources found", color: "cyan" },
  { icon: FileText, label: "Reading documents", detail: "2 PDFs · 41 chunks", color: "emerald" },
  { icon: Star, label: "Ranking evidence", detail: "17 relevant · 4 discarded", color: "orange" },
] as const;

const SEARCH_RESULTS = [
  { page: "[1]", title: "LangGraph docs — StateGraph reference", domain: "langchain-ai.github.io", rel: "0.94" },
  { page: "[2]", title: "CrewAI: role-based multi-agent framework", domain: "docs.crewai.com", rel: "0.91" },
  { page: "[3]", title: "A field guide to multi-agent orchestration", domain: "arxiv.org", rel: "0.87" },
  { page: "[4]", title: "Comparing agent frameworks in production", domain: "medium.com", rel: "0.82" },
];

const ANSWER = [
  "LangGraph is better suited for production systems: StateGraph gives you explicit, testable control over agent state, which matters when you need reproducible runs and recovery from failures. [1][3]",
  "CrewAI wins for rapid prototyping — its role-based Crew + Task abstraction gets a working pipeline up in minutes. [2]",
  "For structured state, per-node metrics, and rollback, LangGraph's explicit graph model is the safer choice. [1][4]",
];

const RECENT_REPORTS = [
  { title: "AI agent frameworks", meta: "2h ago · 21 sources" },
  { title: "RAG architecture trade-offs", meta: "Yesterday · 14 sources" },
  { title: "Local LLM stack survey", meta: "Mon · 9 sources" },
];

const PINNED = ["LLM alignment 2025", "Vector DB benchmarks"];
const SAVED = ['"cross-encoder" reranking', '"state machine" agents'];

function useTypewriter(text: string, startDelay: number, runId: number) {
  const [count, setCount] = useState(0);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    setCount(0);
    setStarted(false);
    const start = setTimeout(() => setStarted(true), startDelay);
    return () => clearTimeout(start);
  }, [startDelay, runId]);

  useEffect(() => {
    if (!started || count >= text.length) return;
    const t = setTimeout(() => setCount((c) => c + 1), 24);
    return () => clearTimeout(t);
  }, [started, count, text.length]);

  return text.slice(0, count);
}

function renderAnswerLine(line: string) {
  const parts = line.split(/(\[\d+\])/g);
  return parts.map((part, i) =>
    /^\[\d+\]$/.test(part) ? (
      <sup key={i} className="ml-0.5 cursor-pointer font-mono text-[8px] text-cyan-300 transition-colors hover:text-cyan-200">
        {part}
      </sup>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

export default function HeroPreview() {
  const [runId, setRunId] = useState(0);
  const [stage, setStage] = useState(-1);
  const [runStats, setRunStats] = useState({ sources: 0, relevant: 0, tokens: 0 });
  const statsStarted = useRef(0);
  const typed = useTypewriter(QUESTION, 700, runId);

  const typingDone = typed.length >= QUESTION.length;
  const showStages = typingDone && stage >= 0 && stage < STAGES.length;
  const showSources = typingDone && stage === STAGES.length;
  const showAnswer = typingDone && stage === STAGES.length + 1;
  const showComplete = typingDone && stage >= STAGES.length + 2;

  useEffect(() => {
    if (!typingDone || stage >= 0) return;
    const timers: ReturnType<typeof setTimeout>[] = [];
    STAGES.forEach((_, i) => {
      timers.push(setTimeout(() => setStage(i), 400 + i * 800));
    });
    timers.push(setTimeout(() => setStage(STAGES.length), 400 + STAGES.length * 800));
    timers.push(setTimeout(() => setStage(STAGES.length + 1), 400 + STAGES.length * 800 + 2600));
    timers.push(setTimeout(() => setStage(STAGES.length + 2), 400 + STAGES.length * 800 + 4200));
    return () => timers.forEach(clearTimeout);
  }, [typingDone, stage, runId]);

  useEffect(() => {
    statsStarted.current = Date.now();
    const iv = setInterval(() => {
      const p = Math.min((Date.now() - statsStarted.current) / 9000, 1);
      setRunStats({
        sources: Math.round(p * 23),
        relevant: Math.round(p * 17),
        tokens: Math.round(p * 11428),
      });
    }, 80);
    return () => clearInterval(iv);
  }, [runId]);

  const replay = () => {
    setRunId((r) => r + 1);
    setStage(-1);
  };

  return (
    <div className="preview-window">
      <div className="preview-bar">
        <div className="flex gap-1.5">
          <span className="preview-dot bg-[#ff5f57]" />
          <span className="preview-dot bg-[#febc2e]" />
          <span className="preview-dot bg-[#28c840]" />
        </div>
        <div className="preview-url">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          localhost · research
        </div>
        <button onClick={replay} className="preview-replay" aria-label="Replay research run">
          <RefreshCw className="h-2.5 w-2.5" />
          Replay
        </button>
      </div>

      <div className="grid lg:grid-cols-[172px_1fr]">
        <aside className="hidden border-r border-white/[0.06] bg-white/[0.012] p-4 lg:block">
          <p className="preview-side-label">RECENT REPORTS</p>
          <div className="mt-2.5 space-y-2">
            {RECENT_REPORTS.map((r) => (
              <div key={r.title}>
                <p className="truncate text-[10px] text-slate-300">{r.title}</p>
                <p className="mt-0.5 text-[8px] text-slate-600">{r.meta}</p>
              </div>
            ))}
          </div>

          <p className="preview-side-label mt-5">PINNED</p>
          <div className="mt-2.5 space-y-1.5">
            {PINNED.map((p) => (
              <p key={p} className="flex items-center gap-1.5 text-[10px] text-slate-400">
                <Pin className="h-2.5 w-2.5 text-slate-600" />
                {p}
              </p>
            ))}
          </div>

          <p className="preview-side-label mt-5">SAVED SEARCHES</p>
          <div className="mt-2.5 space-y-1.5">
            {SAVED.map((s) => (
              <p key={s} className="truncate font-mono text-[9px] text-slate-500">
                {s}
              </p>
            ))}
          </div>
        </aside>

        <div className="space-y-3 p-4 sm:p-5">
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3.5">
            <div className="flex items-center justify-between">
              <p className="preview-question-label">RESEARCH QUESTION</p>
              <span className="text-[9px] text-emerald-400">just now</span>
            </div>
            <p className="mt-2 min-h-[40px] text-[13px] font-medium leading-5 text-slate-100">
              {typed}
              {!typingDone && <span className="typing-caret" />}
            </p>
            <div className="mt-3 flex items-center gap-2">
              <span className="preview-chip">Web</span>
              <span className="preview-chip">Deep research</span>
              <span className="ml-auto flex h-6 w-6 items-center justify-center rounded-md bg-violet-500/90 text-white">
                <ArrowRight className="h-3 w-3" />
              </span>
            </div>
          </div>

          <div className="min-h-[236px] rounded-xl border border-white/[0.07] bg-[#111] p-3.5">
            {showStages && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Workflow
                </p>
                <div className="mt-3 space-y-2.5">
                  {STAGES.map(({ icon: Icon, label, detail, color }, i) => (
                    <div key={label} className="flex items-center gap-2.5">
                      <span className={`preview-stage-icon preview-stage-${color} ${i > stage ? "opacity-40" : ""}`}>
                        {i < stage ? <Check className="h-3 w-3" /> : <Icon className="h-3 w-3" />}
                      </span>
                      <div className="flex flex-1 items-center justify-between">
                        <span className={`text-[11px] ${i <= stage ? "text-slate-200" : "text-slate-600"}`}>
                          {label}
                        </span>
                        <span className="font-mono text-[9px] text-slate-600">
                          {i < stage ? "✓" : i === stage ? detail : "—"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <AnimatePresence>
              {showSources && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Sources · 4 of 21
                  </p>
                  <div className="mt-3 space-y-1.5">
                    {SEARCH_RESULTS.map((s, i) => (
                      <motion.div
                        key={s.page}
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.22 }}
                        className="flex items-baseline gap-2.5 rounded-lg border border-white/[0.05] bg-white/[0.02] px-2.5 py-2"
                      >
                        <span className="font-mono text-[9px] text-cyan-300">{s.page}</span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[10px] text-slate-300">{s.title}</p>
                          <p className="truncate font-mono text-[8px] text-slate-600">{s.domain}</p>
                        </div>
                        <span className="font-mono text-[8px] text-emerald-400">{s.rel}</span>
                      </motion.div>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence>
              {showAnswer && (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-violet-300">
                    Cited answer
                  </p>
                  <div className="mt-2.5 space-y-2">
                    {ANSWER.map((line, i) => (
                      <motion.p
                        key={i}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.1 + i * 0.22 }}
                        className="text-[11px] leading-[1.7] text-slate-400"
                      >
                        {renderAnswerLine(line)}
                      </motion.p>
                    ))}
                  </div>
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.8 }}
                    className="mt-3 space-y-1.5 border-t border-white/[0.06] pt-3"
                  >
                    {SEARCH_RESULTS.map((s) => (
                      <div key={s.page} className="flex items-baseline gap-2">
                        <span className="font-mono text-[9px] text-cyan-300">{s.page}</span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[10px] text-slate-300">{s.title}</p>
                          <p className="truncate font-mono text-[8px] text-slate-600">{s.domain}</p>
                        </div>
                        <span className="rounded border border-emerald-400/20 bg-emerald-400/5 px-1.5 py-0.5 text-[7px] uppercase tracking-wide text-emerald-400">
                          Cited
                        </span>
                      </div>
                    ))}
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>

            {!showStages && !showSources && !showAnswer && !showComplete && (
              <div className="flex h-[204px] items-center justify-center">
                <p className="text-[10px] text-slate-600">Waiting for question…</p>
              </div>
            )}

            <AnimatePresence>
              {showComplete && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4 }}
                  className="mt-3 rounded-lg border border-emerald-400/15 bg-emerald-400/[0.04] px-3 py-2.5"
                >
                  <div className="flex items-center gap-2">
                    <span className="flex h-4.5 w-4.5 items-center justify-center rounded-full bg-emerald-400/15 text-emerald-300">
                      <Check className="h-2.5 w-2.5" />
                    </span>
                    <p className="text-[10px] font-semibold text-emerald-300">
                      Research complete
                    </p>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[8px] text-slate-400">
                    <span>23 sources verified</span>
                    <span>7 citations</span>
                    <span>Confidence 94%</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="preview-metric">
              <span>Sources</span>
              <strong>{runStats.sources}</strong>
            </div>
            <div className="preview-metric">
              <span>Relevant</span>
              <strong>{runStats.relevant}</strong>
            </div>
            <div className="preview-metric">
              <span>Tokens</span>
              <strong>{runStats.tokens.toLocaleString()}</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
