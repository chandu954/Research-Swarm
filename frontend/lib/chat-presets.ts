import {
  BrainCircuit,
  FileCheck2,
  FileSearch,
  FileText,
  FolderOpen,
  Github,
  Globe2,
  Scale,
  Search,
  Sparkles,
} from "lucide-react";

export function timeAgo(iso: string): string {
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

export const suggestions = [
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

export type ResearchMode = (typeof researchModes)[number];

export const researchModes = [
  { label: "Deep Research", directive: "Deep research:", hint: "Plan, search many sources, rank evidence", icon: Sparkles },
  { label: "Compare", directive: "Compare:", hint: "Trade-offs across candidates", icon: Scale },
  { label: "Think Longer", directive: "Think longer:", hint: "Extra depth per source", icon: BrainCircuit },
  { label: "GitHub", directive: "GitHub:", hint: "Focus on repositories", icon: Github },
] as const;

export const capabilities = [
  { label: "Web search", icon: Globe2, tint: "bg-cyan-400/10 text-cyan-400" },
  { label: "PDF analysis", icon: FileText, tint: "bg-emerald-400/10 text-emerald-400" },
  { label: "GitHub research", icon: Github, tint: "bg-orange-400/10 text-orange-400" },
  { label: "Local files", icon: FolderOpen, tint: "bg-amber-400/10 text-amber-400" },
  { label: "Multi-agent planning", icon: BrainCircuit, tint: "bg-violet-400/10 text-violet-400" },
  { label: "Cited reports", icon: FileCheck2, tint: "bg-blue-400/10 text-blue-400" },
] as const;

export const rotatingPlaceholders = [
  "Compare GPT-5 vs Claude",
  "Analyze uploaded PDFs",
  "Review a GitHub repository",
  "Research LangGraph",
  "Find AI startup competitors",
  "Generate a literature review",
  "Track the latest AI agent frameworks",
] as const;
