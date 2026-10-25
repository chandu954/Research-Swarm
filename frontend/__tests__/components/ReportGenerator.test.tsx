import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ReportGenerator from "@/components/ReportGenerator";
import type { Message, SourceCitation } from "@/lib/types";

vi.mock("@/components/ExportMenu", () => ({
  default: ({ document, options }: { document: { markdown: string; metadata: Record<string, unknown> }; options: { cover: boolean; toc: boolean } }) => (
    <output data-testid="export-document" data-options={JSON.stringify(options)}>
      {JSON.stringify(document)}
    </output>
  ),
}));

const sources = [{ title: "Research source", url: "https://example.org" }] as SourceCitation[];
const messages: Message[] = [
  { id: "q", role: "user", content: "Research topic", timestamp: 1 },
  { id: "a", role: "assistant", content: "## Findings\nStrong improvement and growth.\n\n## Risks\nRegulatory concerns.", timestamp: 2 },
];

describe("ReportGenerator", () => {
  it("stays hidden without a completed assistant answer", () => {
    const { container } = render(<ReportGenerator query="topic" messages={[
      { id: "thinking", role: "assistant", content: "Thinking...", timestamp: 1 },
    ]} sources={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("creates an executive summary and includes source metadata", () => {
    render(<ReportGenerator query="Research topic" messages={messages} sources={sources} />);
    expect(screen.getByText(/Key Findings/)).toBeInTheDocument();
    const exported = JSON.parse(screen.getByTestId("export-document").textContent || "{}");
    expect(exported.title).toBe("Research topic");
    expect(exported.markdown).toContain("Strong improvement and growth.");
    expect(exported.metadata).toMatchObject({ template: "executive", sources: 1 });
  });

  it("builds a technical table of contents and supports print options", () => {
    render(<ReportGenerator query="Topic" messages={messages} sources={sources} />);
    fireEvent.click(screen.getByRole("button", { name: /technical report/i }));

    const exported = JSON.parse(screen.getByTestId("export-document").textContent || "{}");
    expect(exported.markdown).toContain("## Table of Contents");
    expect(exported.markdown).toContain("[Findings](#section-0)");
    expect(exported.markdown).toContain("## Methodology");
    expect(exported.metadata.template).toBe("technical");
    expect(screen.getByTestId("export-document")).toHaveAttribute("data-options", '{"cover":true,"toc":true}');

    fireEvent.click(screen.getByLabelText("Cover page"));
    expect(screen.getByTestId("export-document")).toHaveAttribute("data-options", '{"cover":false,"toc":true}');
  });

  it("classifies section headings into SWOT categories and includes the full answer", () => {
    render(<ReportGenerator query="Topic" messages={messages} sources={sources} />);
    fireEvent.click(screen.getByRole("button", { name: /swot analysis/i }));

    const exported = JSON.parse(screen.getByTestId("export-document").textContent || "{}");
    expect(exported.markdown).toContain("## Strengths\n\n- Findings");
    expect(exported.markdown).toContain("## Opportunities\n\n- Findings");
    expect(exported.markdown).toContain("## Threats\n\n- Risks");
    expect(exported.markdown).toContain("### Full Analysis");
    expect(exported.metadata.template).toBe("swot");
  });
});
