"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import {
  BarChart3,
  BrainCircuit,
  FileDown,
  Lightbulb,
  Scale,
} from "lucide-react";
import { cn } from "@/lib/utils";

function extractKeywords(text: string): string[] {
  const stopWords = new Set([
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "shall", "can", "this", "that", "these", "those",
    "it", "its", "they", "them", "their", "we", "you", "he", "she",
    "not", "no", "nor", "but", "if", "so", "as", "than", "then",
    "also", "very", "just", "about", "above", "after", "again", "all",
    "each", "every", "more", "most", "other", "some", "such", "only",
    "own", "same", "too", "under", "up", "with", "what", "which",
    "who", "how", "why", "where", "when",
  ]);

  const words = text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .split(/\s+/)
    .filter((w) => w.length > 3 && !stopWords.has(w));

  const freq: Record<string, number> = {};
  for (const w of words) {
    freq[w] = (freq[w] || 0) + 1;
  }

  return Object.entries(freq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([w]) => w);
}

const actions = [
  {
    label: "Compare",
    icon: Scale,
    tint: "bg-violet-500/10 text-violet-300",
    template: (topic: string) =>
      `Compare ${topic} against alternatives across pricing, benchmarks, and trade-offs`,
  },
  {
    label: "Deep dive",
    icon: BrainCircuit,
    tint: "bg-cyan-500/10 text-cyan-300",
    template: (topic: string) =>
      `Deep dive into ${topic} — architecture, caveats, and implementation details`,
  },
  {
    label: "Benchmarks",
    icon: BarChart3,
    tint: "bg-emerald-500/10 text-emerald-300",
    template: (topic: string) =>
      `Show the latest benchmarks and quantitative metrics for ${topic}`,
  },
  {
    label: "Explain",
    icon: Lightbulb,
    tint: "bg-amber-500/10 text-amber-300",
    template: (topic: string) =>
      `Explain how ${topic} works step by step, with cited evidence`,
  },
  {
    label: "Report",
    icon: FileDown,
    tint: "bg-orange-500/10 text-orange-300",
    template: (topic: string) =>
      `Generate a complete cited report on ${topic} covering findings, risks, and outlook`,
  },
] as const;

interface FollowUpSuggestionsProps {
  answer: string;
  onSelect: (query: string) => void;
}

export default function FollowUpSuggestions({ answer, onSelect }: FollowUpSuggestionsProps) {
  const suggestions = useMemo(() => {
    const keywords = extractKeywords(answer);
    if (keywords.length === 0) return [];

    const used = new Set<string>();
    const result: { label: string; prompt: string }[] = [];

    for (const action of actions) {
      const topic = keywords[result.length % keywords.length];
      const prompt = action.template(topic);
      if (!used.has(prompt) && prompt.length < 120) {
        used.add(prompt);
        result.push({ label: action.label, prompt });
      }
      if (result.length >= 4) break;
    }

    return result;
  }, [answer]);

  const actionByLabel = useMemo(
    () => Object.fromEntries(actions.map((a) => [a.label, a])) as Record<string, (typeof actions)[number]>,
    [],
  );

  if (suggestions.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6 mt-8"
    >
      <div className="mb-3 flex items-center gap-2">
        <Lightbulb className="h-3.5 w-3.5 text-amber-400" />
        <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Follow-up actions
        </span>
      </div>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {suggestions.map(({ label, prompt }) => {
          const action = actionByLabel[label];
          const Icon = action?.icon ?? Scale;
          return (
            <button
              key={prompt}
              type="button"
              onClick={() => onSelect(prompt)}
              className="group flex items-center gap-2.5 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5 text-left transition-all hover:-translate-y-px hover:border-violet-400/25 hover:bg-violet-500/[0.04]"
            >
              <span
                className={cn(
                  "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg transition-transform group-hover:scale-105",
                  action?.tint,
                )}
              >
                <Icon className="h-3.5 w-3.5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[10px] font-semibold text-[var(--text-primary)]">
                  {label}
                </span>
                <span className="block truncate text-[10px] text-[var(--text-muted)]">
                  {prompt}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </motion.div>
  );
}
