import { describe, it, expect } from "vitest";
import {
  buildUsedInMap,
  countCitationOccurrences,
  extractCitedIndices,
  formatEvidenceScore,
  parseCitationSegments,
  parseReferences,
  splitSections,
  computeEvidenceScore,
  sourceEvidenceScore,
  type CitationSegment,
} from "@/lib/report-citations";

describe("parseCitationSegments", () => {
  it("splits [Source N] markers into citation segments", () => {
    const segments = parseCitationSegments(
      "RAG combines retrieval [Source 1] with generation [Source 2].",
    );
    expect(segments).toEqual([
      { type: "text", value: "RAG combines retrieval " },
      { type: "citation", indices: [1] },
      { type: "text", value: " with generation " },
      { type: "citation", indices: [2] },
      { type: "text", value: "." },
    ]);
  });

  it("supports bare [N] markers", () => {
    const segments = parseCitationSegments("Findings [1] and [2].");
    expect(segments).toEqual([
      { type: "text", value: "Findings " },
      { type: "citation", indices: [1] },
      { type: "text", value: " and " },
      { type: "citation", indices: [2] },
      { type: "text", value: "." },
    ]);
  });

  it("handles multi-index markers [Source 1, 3]", () => {
    const segments = parseCitationSegments("Claim [Source 1, 3] supported.");
    expect(segments).toContainEqual({ type: "citation", indices: [1, 3] });
  });

  it("does not treat real markdown links as citations", () => {
    const segments = parseCitationSegments("See [docs](https://x.dev) and [1](https://x.dev).");
    const citations = segments.filter((s): s is Extract<CitationSegment, { type: "citation" }> => s.type === "citation");
    expect(citations).toHaveLength(0);
  });

  it("returns plain text when no markers exist", () => {
    expect(parseCitationSegments("No citations here.")).toEqual([
      { type: "text", value: "No citations here." },
    ]);
  });

  it("ignores non-positive indices", () => {
    const segments = parseCitationSegments("[Source 0] and [Source 2].");
    const citations = segments.filter((s): s is Extract<CitationSegment, { type: "citation" }> => s.type === "citation");
    expect(citations).toEqual([{ type: "citation", indices: [2] }]);
  });
});

describe("extractCitedIndices", () => {
  it("returns distinct cited indices in order", () => {
    expect(extractCitedIndices("[Source 3] ... [Source 1] ... [Source 3]")).toEqual([3, 1]);
  });

  it("ignores reference-list markers in a References section", () => {
    const md =
      "Claim [Source 1] and [Source 2].\n\n## References\n\n[1] RAG paper — https://arxiv.org/abs/2005.11401\n[2] Another paper — https://arxiv.org/abs/2101.00000";
    expect(extractCitedIndices(md)).toEqual([1, 2]);
  });
});

describe("splitSections", () => {
  it("splits h1-h3 headings into sections", () => {
    const sections = splitSections("# Intro\n\nhello\n\n## Details\n\nbody\n\n### Sub\n\ndeeper");
    expect(sections.map((s) => s.heading)).toEqual(["Intro", "Details", "Sub"]);
    expect(sections[0].content).toContain("hello");
    expect(sections[1].content).toContain("body");
    expect(sections[2].content).toContain("deeper");
  });

  it("keeps h4+ inline with the current section", () => {
    const sections = splitSections("## Overview\n\ntext\n\n#### Note\n\nmore");
    expect(sections).toHaveLength(1);
    expect(sections[0].content).toContain("#### Note");
  });

  it("handles leading content without a heading", () => {
    const sections = splitSections("lead in\n\n## Next\n\nbody");
    expect(sections[0].heading).toBeNull();
    expect(sections[0].content).toContain("lead in");
    expect(sections[1].heading).toBe("Next");
  });
});

describe("computeEvidenceScore", () => {
  it("uses hybrid_score when present", () => {
    const score = sourceEvidenceScore({ source_type: "web", title: "t", hybrid_score: 0.85 });
    expect(score).toBe(8.5);
  });

  it("falls back to null without hybrid_score", () => {
    expect(sourceEvidenceScore({ source_type: "web", title: "t" })).toBeNull();
  });

  it("clamps to 0-10", () => {
    expect(sourceEvidenceScore({ source_type: "web", title: "t", hybrid_score: 1.4 })).toBe(10);
  });

  it("combines source quality with citation coverage", () => {
    const sources = [
      { source_type: "web", title: "a", hybrid_score: 0.9 },
      { source_type: "web", title: "b", hybrid_score: 0.7 },
    ];
    const full = computeEvidenceScore(sources, [1, 2]);
    expect(full.overall).toBeCloseTo(8.0);
    expect(full.label).toBe("Strong");
    expect(full.coverage).toBe(1);

    const partial = computeEvidenceScore(sources, [1]);
    expect(partial.overall).toBeLessThan(full.overall);
    expect(partial.coverage).toBe(0.5);
  });

  it("returns Weak for empty sources", () => {
    const result = computeEvidenceScore([], []);
    expect(result.overall).toBe(0);
    expect(result.label).toBe("Weak");
  });
});

describe("countCitationOccurrences", () => {
  it("counts how many times each source index is cited", () => {
    const counts = countCitationOccurrences("[Source 1] ... [Source 2] ... [Source 1]");
    expect(counts.get(1)).toBe(2);
    expect(counts.get(2)).toBe(1);
    expect(counts.get(3)).toBeUndefined();
  });

  it("ignores citations in References section", () => {
    const md = "See [Source 1].\n\n## References\n\n[1] paper\n[2] paper";
    const counts = countCitationOccurrences(md);
    expect(counts.get(1)).toBe(1);
    expect(counts.get(2)).toBeUndefined();
  });

  it("returns empty map for no citations", () => {
    expect(countCitationOccurrences("no citations here")).toEqual(new Map());
  });
});

describe("formatEvidenceScore", () => {
  it("formats score to one decimal", () => {
    expect(formatEvidenceScore(8.5)).toBe("8.5");
    expect(formatEvidenceScore(7)).toBe("7.0");
    expect(formatEvidenceScore(0)).toBe("0.0");
  });
});

describe("parseReferences", () => {
  it("parses markdown link references", () => {
    const entries = parseReferences("[RAG paper](https://arxiv.org/abs/1) — a survey\n[Another](https://arxiv.org/abs/2)");
    expect(entries).toHaveLength(2);
    expect(entries[0]).toMatchObject({ index: 1, title: "RAG paper", url: "https://arxiv.org/abs/1" });
    expect(entries[1]).toMatchObject({ index: 2, title: "Another", url: "https://arxiv.org/abs/2" });
  });

  it("parses plain URL lines", () => {
    const entries = parseReferences("https://example.com/paper some description");
    expect(entries).toHaveLength(1);
    expect(entries[0].url).toBe("https://example.com/paper");
  });

  it("skips empty lines", () => {
    const entries = parseReferences("\n\n\n");
    expect(entries).toEqual([]);
  });

  it("treats uncategorized text as a reference entry", () => {
    const entries = parseReferences("Just a title with no link");
    expect(entries).toHaveLength(1);
    expect(entries[0].title).toBe("Just a title with no link");
  });
});

describe("buildUsedInMap", () => {
  it("maps source indices to section headings that cite them", () => {
    const sources = [
      { source_type: "web", title: "a", hybrid_score: 0.5 },
      { source_type: "web", title: "b", hybrid_score: 0.5 },
    ];
    const usedSections = [
      { index: 1, heading: "Findings", content: "See [Source 1] here." },
      { index: 2, heading: "Analysis", content: "See [Source 2] and [Source 1]." },
    ];
    const map = buildUsedInMap(sources, usedSections);
    expect(map.get(1)).toEqual(["Findings", "Analysis"]);
    expect(map.get(2)).toEqual(["Analysis"]);
  });

  it("ignores sections without headings", () => {
    const sources = [{ source_type: "web", title: "a", hybrid_score: 0.5 }];
    const usedSections = [{ index: 1, heading: null, content: "See [Source 1]." }];
    const map = buildUsedInMap(sources, usedSections);
    expect(map.size).toBe(0);
  });

  it("ignores out-of-range indices", () => {
    const sources = [{ source_type: "web", title: "a", hybrid_score: 0.5 }];
    const usedSections = [{ index: 1, heading: "Findings", content: "See [Source 99]." }];
    const map = buildUsedInMap(sources, usedSections);
    expect(map.size).toBe(0);
  });
});
