"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Lightbulb, Sparkles } from "lucide-react";

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

const suggestionTemplates = [
  (topic: string) => `Compare ${topic} with alternative approaches in detail`,
  (topic: string) => `What are the limitations and challenges of ${topic}?`,
  (topic: string) => `Explain the architecture and implementation of ${topic}`,
  (topic: string) => `What are the latest research breakthroughs in ${topic}?`,
  (topic: string) => `How does ${topic} compare across different frameworks?`,
  (topic: string) => `What are the real-world applications of ${topic}?`,
  (topic: string) => `What future developments are expected for ${topic}?`,
  (topic: string) => `Create a detailed implementation guide for ${topic}`,
];

interface FollowUpSuggestionsProps {
  answer: string;
  onSelect: (query: string) => void;
}

export default function FollowUpSuggestions({ answer, onSelect }: FollowUpSuggestionsProps) {
  const suggestions = useMemo(() => {
    const keywords = extractKeywords(answer);
    if (keywords.length === 0) return [];

    const used = new Set<string>();
    const result: string[] = [];

    for (const template of suggestionTemplates) {
      const topic = keywords[result.length % keywords.length];
      const suggestion = template(topic);
      if (!used.has(suggestion) && suggestion.length < 120) {
        used.add(suggestion);
        result.push(suggestion);
      }
      if (result.length >= 4) break;
    }

    return result;
  }, [answer]);

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
          Follow-up questions
        </span>
      </div>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onSelect(suggestion)}
            className="group flex items-start gap-2 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5 text-left text-[11px] text-[var(--text-secondary)] transition-all hover:border-violet-400/20 hover:bg-violet-500/[0.04] hover:text-[var(--text-primary)]"
          >
            <Sparkles className="mt-0.5 h-3 w-3 flex-shrink-0 text-violet-400 opacity-0 transition-opacity group-hover:opacity-100" />
            <span className="flex-1 leading-snug">{suggestion}</span>
            <ArrowRight className="mt-0.5 h-3 w-3 flex-shrink-0 text-[var(--text-muted)] opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100" />
          </button>
        ))}
      </div>
    </motion.div>
  );
}
