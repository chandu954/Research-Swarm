import { describe, expect, it } from "vitest";
import { buildReportHTML, buildReportJSON, buildReportMarkdown, reportFilename } from "@/lib/export-report";

const doc = {
  title: "A <Safe> Report",
  markdown: "## Findings\n- **Evidence** — reliable\n- Plain item\n1. Ordered item\n> Quote\n---\n### Details\nText & more",
  sources: [{ source_type: "web", title: "Source <one>", url: "https://example.com/?a=1&b=2" }],
  metadata: { execution_time_ms: 1250 },
};

describe("report exports", () => {
  it("creates a clean markdown appendix and filename", () => {
    const markdown = buildReportMarkdown(doc);
    expect(markdown).toContain("# A <Safe> Report");
    expect(markdown).toContain("**Sources cited:** 1");
    expect(markdown).toContain("[Source <one>](https://example.com/?a=1&b=2)");
    expect(reportFilename("  Résumé / AI? ")).toBe("rsum-ai");
    expect(reportFilename("!!!")).toBe("research-report");
  });

  it("escapes HTML, builds a linked contents page, and honors disabled options", () => {
    const html = buildReportHTML(doc);
    expect(html).toContain("A &lt;Safe&gt; Report");
    expect(html).toContain("Table of Contents");
    expect(html).toContain("href=\"#section-0\"");
    expect(html).toContain("Evidence</strong> —  reliable");
    expect(html).toContain("Text &amp; more");
    expect(html).not.toContain("<script>");

    const compact = buildReportHTML(doc, { cover: false, toc: false });
    expect(compact).not.toContain("Table of Contents");
    expect(compact).not.toContain("page-break-after:always;text-align:center");
  });

  it("serializes JSON metadata and supplies safe defaults", () => {
    const parsed = JSON.parse(buildReportJSON(doc));
    expect(parsed).toMatchObject({ title: doc.title, sources: doc.sources, metadata: doc.metadata });
    expect(parsed.generated_by).toBe("ResearchSwarm AI");
    expect(parsed.markdown).toContain("## Sources");

    const empty = JSON.parse(buildReportJSON({ title: "Empty", markdown: "Body" }));
    expect(empty.sources).toEqual([]);
    expect(empty.metadata).toEqual({});
  });
});
