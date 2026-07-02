import type { ReactNode } from "react";
import {
  BrainCircuit,
  Globe2,
  FileText,
  Sparkles,
  Search,
  Merge,
} from "lucide-react";

export interface AgentConfig {
  key: string;
  label: string;
  icon: React.ElementType;
  color: string;
  gradient: string;
  thinking: string[];
}

export const AGENTS: AgentConfig[] = [
  {
    key: "planner",
    label: "Planner",
    icon: BrainCircuit,
    color: "violet",
    gradient: "from-violet-600 to-purple-600",
    thinking: [
      "Analyzing your query...",
      "Breaking down into subtasks...",
      "Identifying relevant sources...",
      "Building execution plan...",
      "Prioritizing research directions...",
    ],
  },
  {
    key: "research_agent",
    label: "Web Research",
    icon: Globe2,
    color: "cyan",
    gradient: "from-cyan-600 to-teal-600",
    thinking: [
      "Searching the web...",
      "Extracting key information...",
      "Ranking search results...",
      "Summarizing findings...",
      "Cross-referencing sources...",
    ],
  },
  {
    key: "document_agent",
    label: "Document Analysis",
    icon: FileText,
    color: "emerald",
    gradient: "from-emerald-600 to-green-600",
    thinking: [
      "Loading documents...",
      "Chunking text content...",
      "Computing embeddings...",
      "Retrieving relevant passages...",
      "Reranking by relevance...",
    ],
  },
  {
    key: "answer_agent",
    label: "Answer Synthesis",
    icon: Sparkles,
    color: "orange",
    gradient: "from-orange-600 to-amber-600",
    thinking: [
      "Gathering evidence...",
      "Structuring the answer...",
      "Citing sources...",
      "Fact-checking claims...",
      "Polishing final response...",
    ],
  },
  {
    key: "verifier",
    label: "Verifier",
    icon: Search,
    color: "rose",
    gradient: "from-rose-600 to-pink-600",
    thinking: [
      "Checking conflicting claims...",
      "Validating source credibility...",
      "Cross-referencing facts...",
    ],
  },
  {
    key: "merge",
    label: "Merge",
    icon: Merge,
    color: "amber",
    gradient: "from-amber-600 to-yellow-600",
    thinking: [
      "Combining research results...",
      "Reconciling differences...",
    ],
  },
];

export const AGENT_ORDER = ["planner", "research_agent", "document_agent", "answer_agent"];

export const AGENT_MAP = Object.fromEntries(
  AGENTS.map((a) => [a.key, a]),
) as Record<string, AgentConfig>;

export const colorStyles: Record<string, { running: string; done: string }> = {
  violet: { running: "border-violet-400/20 bg-violet-500/10 text-violet-300", done: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300" },
  cyan: { running: "border-cyan-400/20 bg-cyan-500/10 text-cyan-300", done: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300" },
  emerald: { running: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300", done: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300" },
  orange: { running: "border-orange-400/20 bg-orange-500/10 text-orange-300", done: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300" },
  rose: { running: "border-rose-400/20 bg-rose-500/10 text-rose-300", done: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300" },
  amber: { running: "border-amber-400/20 bg-amber-500/10 text-amber-300", done: "border-emerald-400/20 bg-emerald-500/10 text-emerald-300" },
};

export const bgStyles: Record<string, string> = {
  violet: "bg-violet-500/[0.06]", cyan: "bg-cyan-500/[0.06]", emerald: "bg-emerald-500/[0.06]",
  orange: "bg-orange-500/[0.06]", rose: "bg-rose-500/[0.06]", amber: "bg-amber-500/[0.06]",
};
