"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, FileText, Globe2, Star } from "lucide-react";

type Example = {
  id: string;
  question: string;
  tags: string[];
  accent: string;
  sources: number;
  time: string;
  wide?: boolean;
  brief: string;
  answer: { label: string; body: string }[];
  citations: string[];
};

const EXAMPLES: Example[] = [
  {
    id: "langgraph",
    question: "Compare LangGraph and CrewAI for production systems.",
    tags: ["Web", "Deep research"],
    accent: "violet",
    sources: 21,
    time: "6.4s",
    wide: true,
    brief: "Which abstraction survives contact with production — explicit graphs or role-based crews?",
    answer: [
      {
        label: "Summary",
        body: "LangGraph is the safer choice for production: explicit state and per-node control make runs reproducible and recoverable. CrewAI prototypes faster, but its role abstractions compress behavior in ways that are harder to test and debug at scale.",
      },
      {
        label: "CrewAI",
        body: "Gentler learning curve, role-based Crew + Task model, faster to first working pipeline. Weaker isolation between steps; behavior hides in decorators and tool callbacks.",
      },
      {
        label: "LangGraph",
        body: "Explicit StateGraph with typed state, checkpoints for resume/rollback, per-node metrics and tracing. More boilerplate up front, but every edge is testable.",
      },
    ],
    citations: ["langchain.ai/blog", "arxiv.org/abs/2404.11584", "docs.crewai.com"],
  },
  {
    id: "postgres",
    question: "PostgreSQL vs MongoDB — which fits an analytics workload?",
    tags: ["Web"],
    accent: "cyan",
    sources: 14,
    time: "5.1s",
    brief: "A decision summary with trade-offs for each workload.",
    answer: [
      {
        label: "Summary",
        body: "PostgreSQL wins for analytics on relational data: mature window functions, materialized views, and pgvector. MongoDB wins when the schema changes often and you need horizontal scale-out with replica sets.",
      },
      {
        label: "When Postgres",
        body: "Joins across entities, SQL tooling, transactional consistency, vector search without a second system.",
      },
      {
        label: "When MongoDB",
        body: "Document-shaped data, fast iteration on schema, sharding beyond a single node.",
      },
    ],
    citations: ["postgresql.org/docs", "mongodb.com/docs", "db-engines.com"],
  },
  {
    id: "pdfs",
    question: "Summarize these 3 papers and find where they disagree.",
    tags: ["PDF", "Documents"],
    accent: "emerald",
    sources: 3,
    time: "8.2s",
    brief: "Reads the PDFs, extracts claims, and flags disagreements.",
    answer: [
      {
        label: "Common ground",
        body: "All three papers agree that evaluation benchmarks are saturating and that human preference data remains the bottleneck for alignment research.",
      },
      {
        label: "Disagreement",
        body: "Paper A argues preference data should be synthetic at scale; Paper B argues synthetic data compounds reward hacking. Paper C takes a middle position with filtered synthetic data.",
      },
    ],
    citations: ["paper-a.pdf · p.4", "paper-b.pdf · p.7", "paper-c.pdf · p.2"],
  },
  {
    id: "alignment",
    question: "What changed in LLM alignment since RLHF?",
    tags: ["Web", "Deep research"],
    accent: "orange",
    sources: 18,
    time: "7.3s",
    brief: "Tracks how the field moved beyond RLHF, with cited developments.",
    answer: [
      {
        label: "Summary",
        body: "Alignment has shifted from reward-model pipelines to direct optimization: DPO removed the explicit reward model, and iterative variants (IPO, KTO) target stability. Constitutional AI moved feedback from humans to principles.",
      },
    ],
    citations: ["arxiv.org/abs/2305.18290", "arxiv.org/abs/2310.12036", "openai.com/constitutional"],
  },
];

export default function ResearchExamples() {
  const [openId, setOpenId] = useState<string | null>("langgraph");
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="examples-scroll">
      {EXAMPLES.map((ex) => {
        const isOpen = openId === ex.id;
        const isExpanded = expanded === ex.id;
        return (
          <article
            key={ex.id}
            className={`example-card ${ex.wide ? "lg:col-span-4" : "lg:col-span-2"} ${
              isOpen ? "example-card-open" : ""
            }`}
          >
            <div className="flex h-full flex-col">
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-wrap gap-1.5">
                  {ex.tags.map((t) => (
                    <span key={t} className="example-tag">
                      {t}
                    </span>
                  ))}
                </div>
                <span className={`example-accent example-accent-${ex.accent}`} />
              </div>

              <h3 className="mt-4 text-[15px] font-medium leading-6 text-white">
                “{ex.question}”
              </h3>
              <p className="mt-2 text-xs leading-5 text-slate-400">{ex.brief}</p>

              <div className="mt-5 flex items-center gap-4 text-[10px] text-slate-400">
                <span className="flex items-center gap-1.5">
                  <Globe2 className="h-3 w-3 text-slate-600" />
                  {ex.sources} sources
                </span>
                <span className="flex items-center gap-1.5">
                  <Star className="h-3 w-3 text-slate-600" />
                  {ex.time}
                </span>
              </div>

              <div className="mt-auto pt-5">
                <button
                  onClick={() => {
                    setOpenId(isOpen ? null : ex.id);
                    setExpanded(isExpanded ? null : ex.id);
                  }}
                  className={`example-toggle ${isOpen ? "example-toggle-active" : ""}`}
                  aria-expanded={isOpen}
                >
                  {isOpen ? "Collapse result" : "See the report"}
                  <ChevronDown className={`h-3.5 w-3.5 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                </button>

                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3 }}
                      className="overflow-hidden"
                    >
                      <div className="space-y-2.5 border-t border-white/[0.06] pt-4">
                        {ex.answer.map((a) => (
                          <div key={a.label}>
                            <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                              <Check className="h-3 w-3 text-emerald-400" />
                              {a.label}
                            </p>
                            <p className="mt-1.5 text-[11px] leading-[1.7] text-slate-400">
                              {a.body}
                            </p>
                          </div>
                        ))}
                        <div className="pt-1">
                          {ex.citations.map((c) => (
                            <p key={c} className="truncate font-mono text-[9px] text-cyan-300/80">
                              ↑ {c}
                            </p>
                          ))}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
