import type { SourceCitation } from "@/lib/types";
import { visit, SKIP } from "unist-util-visit";
import type { Root } from "mdast";

export type CitationSegment =
  | { type: "text"; value: string }
  | { type: "citation"; indices: number[] };

const CITATION_RE =
  /\[(?:Source\s+)?(\d+(?:\s*,\s*\d+)*)\](?!\s*\()/gi;

export function parseCitationSegments(text: string): CitationSegment[] {
  const segments: CitationSegment[] = [];
  let cursor = 0;
  let match: RegExpExecArray | null;
  const re = new RegExp(CITATION_RE.source, "gi");
  while ((match = re.exec(text)) !== null) {
    if (match.index > cursor) {
      segments.push({ type: "text", value: text.slice(cursor, match.index) });
    }
    const indices = match[1]
      .split(",")
      .map((part) => parseInt(part.trim(), 10))
      .filter((n) => Number.isFinite(n) && n > 0);
    if (indices.length > 0) {
      segments.push({ type: "citation", indices });
    }
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) {
    segments.push({ type: "text", value: text.slice(cursor) });
  }
  return segments.length > 0 ? segments : [{ type: "text", value: text }];
}

export function extractCitedIndices(markdown: string): number[] {
  const body = splitSections(markdown)
    .filter((section) => !section.heading || !/^(references|sources)$/i.test(section.heading))
    .map((section) => section.content)
    .join("\n");
  const seen = new Set<number>();
  const result: number[] = [];
  for (const segment of parseCitationSegments(body)) {
    if (segment.type === "citation") {
      for (const idx of segment.indices) {
        if (!seen.has(idx)) {
          seen.add(idx);
          result.push(idx);
        }
      }
    }
  }
  return result;
}

export interface ReportSection {
  level: number;
  heading: string | null;
  content: string;
}

const HEADING_RE = /^(#{1,3})\s+(.+?)\s*#*\s*$/;

export function splitSections(markdown: string): ReportSection[] {
  const lines = markdown.split("\n");
  const sections: ReportSection[] = [];
  let current: ReportSection = { level: 0, heading: null, content: "" };

  const flush = () => {
    if (current.content.trim() || current.heading) {
      sections.push(current);
    }
  };

  for (const line of lines) {
    const match = HEADING_RE.exec(line);
    if (match) {
      flush();
      current = {
        level: match[1].length,
        heading: match[2].trim(),
        content: "",
      };
    } else {
      current.content += line + "\n";
    }
  }
  flush();
  return sections;
}

export interface EvidenceScore {
  overall: number;
  label: "Strong" | "Moderate" | "Weak";
  perSource: (number | null)[];
  cited: number[];
  coverage: number;
}

export function sourceEvidenceScore(source: SourceCitation): number | null {
  if (typeof source.hybrid_score === "number" && Number.isFinite(source.hybrid_score)) {
    return Math.min(10, Math.max(0, source.hybrid_score * 10));
  }
  return null;
}

export function computeEvidenceScore(
  sources: SourceCitation[],
  cited: number[],
): EvidenceScore {
  const perSource = sources.map((source) => sourceEvidenceScore(source));
  const scored = perSource.filter((score): score is number => score !== null);
  const citedSet = new Set(cited);
  const coverage = sources.length > 0 ? citedSet.size / sources.length : 0;
  const mean =
    scored.length > 0
      ? scored.reduce((sum, score) => sum + score, 0) / scored.length
      : 0;
  const overall = Math.min(10, Math.round((mean * (0.6 + 0.4 * coverage)) * 10) / 10);
  const label: EvidenceScore["label"] =
    overall >= 7 ? "Strong" : overall >= 4 ? "Moderate" : "Weak";
  return { overall, label, perSource, cited: [...citedSet].sort((a, b) => a - b), coverage };
}

export function formatEvidenceScore(score: number): string {
  return score.toFixed(1);
}

interface CitationTextNode {
  type: "text";
  value: string;
  data?: {
    hName: string;
    hProperties: Record<string, string>;
    hChildren: [{ type: "text"; value: string }];
  };
}

export function remarkCitations() {
  return (tree: Root) => {
    visit(tree, "text", (node, index, parent) => {
      if (!parent || index == null || !node.value) return;
      const matches = [...node.value.matchAll(CITATION_RE)];
      if (matches.length === 0) return;
      const parts: CitationTextNode[] = [];
      let cursor = 0;
      for (const match of matches) {
        const start = match.index ?? 0;
        if (start > cursor) {
          parts.push({ type: "text", value: node.value.slice(cursor, start) });
        }
        const indices = match[1]
          .split(",")
          .map((part) => parseInt(part.trim(), 10))
          .filter((n) => Number.isFinite(n) && n > 0);
        if (indices.length > 0) {
          parts.push({
            type: "text",
            value: " ",
            data: {
              hName: "span",
              hProperties: { "data-citation": indices.join(",") },
              hChildren: [{ type: "text", value: indices.join(",") }],
            },
          });
        }
        cursor = start + match[0].length;
      }
      if (cursor < node.value.length) {
        parts.push({ type: "text", value: node.value.slice(cursor) });
      }
      parent.children.splice(index, 1, ...(parts as never[]));
      return [SKIP, index + parts.length] as const;
    });
  };
}
