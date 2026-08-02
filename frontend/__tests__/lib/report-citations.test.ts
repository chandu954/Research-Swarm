import { describe, it, expect } from "vitest";
import {
  parseCitationSegments,
  extractCitedIndices,
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
