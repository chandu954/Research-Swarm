"use client";

import { motion } from "framer-motion";
import { Check, Search } from "lucide-react";

const NODES = [
  { node: "Planner", model: "Qwen3", detail: "Splits the question into search and retrieval steps.", color: "violet" },
  { node: "Search agent", model: "Llama3", detail: "Queries 18+ sources and extracts claims.", color: "cyan" },
  { node: "Document agent", model: "Gemma3", detail: "Reads PDFs and scores passages with cross-encoder reranking.", color: "emerald" },
  { node: "Synthesizer", model: "Gemma3", detail: "Merges evidence into one cited report.", color: "orange" },
];

function FlowArrow({ delay = 0 }: { delay?: number }) {
  return (
    <div className="architecture-arrow">
      <motion.span
        className="flow-signal"
        animate={{ y: [0, 26], opacity: [0, 1, 0] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut", delay }}
      />
    </div>
  );
}

export default function ArchitectureFlow() {
  return (
    <div className="architecture-flow">
      <div className="architecture-entry">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300">
          <Search className="h-4 w-4" />
        </span>
        <div>
          <p className="text-sm font-medium text-white">Your question</p>
          <p className="mt-0.5 text-xs text-slate-400">
            Sent over HTTP or SSE from the browser
          </p>
        </div>
      </div>

      <FlowArrow delay={0} />

      <div className="arch-grid">
        {NODES.map(({ node, model, detail, color }, i) => (
          <motion.div
            key={node}
            className={`arch-node arch-node-border-${color}`}
            animate={{ opacity: [0.92, 1, 0.92] }}
            transition={{ duration: 2.6, repeat: Infinity, delay: i * 0.65, ease: "easeInOut" }}
          >
            <div className="flex items-center justify-between">
              <p className={`arch-node-title arch-node-${color}`}>{node}</p>
              <span className="arch-node-model">{model}</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-400">{detail}</p>
          </motion.div>
        ))}
      </div>

      <FlowArrow delay={0.4} />

      <div className="architecture-entry">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-emerald-400/20 bg-emerald-400/10 text-emerald-300">
          <Check className="h-4 w-4" />
        </span>
        <div>
          <p className="text-sm font-medium text-white">Cited report</p>
          <p className="mt-0.5 text-xs text-slate-400">
            Numbered references for every claim
          </p>
        </div>
      </div>
    </div>
  );
}
