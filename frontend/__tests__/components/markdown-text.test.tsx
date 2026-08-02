import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

function citationValues(container: HTMLElement): string[] {
  return [...container.querySelectorAll("[data-citation]")].map(
    (el) => el.getAttribute("data-citation") ?? "",
  );
}
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { remarkCitations } from "@/lib/report-citations";

function CitationSpans(props: Record<string, unknown>) {
  const raw = props["data-citation"] as string | undefined;
  if (!raw) return <span {...props} />;
  return <span data-citation={raw}>c</span>;
}

describe("remarkCitations plugin", () => {
  it("turns [Source N] markers into citation spans", () => {
    render(
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkCitations]}
        components={{ span: CitationSpans as never }}
      >
        {"Hybrid deployments reduce latency [Source 1, 2] and cost [Source 1]."}
      </ReactMarkdown>,
    );
    expect(screen.queryByText(/\[Source/)).toBeNull();
    const chips = citationValues(document.body);
    expect(chips).toEqual(["1,2", "1"]);
  });

  it("does not touch real markdown links", () => {
    render(
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkCitations]}
        components={{ span: CitationSpans as never }}
      >
        {"See [docs](https://x.dev) and keep text [Source 2] intact."}
      </ReactMarkdown>,
    );
    const link = screen.getByRole("link", { name: "docs" });
    expect(link).toBeTruthy();
    const chips = citationValues(document.body);
    expect(chips).toEqual(["2"]);
  });

  it("leaves plain paragraphs unchanged", () => {
    render(
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkCitations]}
        components={{ span: CitationSpans as never }}
      >
        {"No citations here."}
      </ReactMarkdown>,
    );
    expect(document.querySelectorAll("[data-citation]")).toHaveLength(0);
    expect(screen.getByText("No citations here.")).toBeTruthy();
  });

  it("does not split inline code or code blocks", () => {
    render(
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkCitations]}
        components={{ span: CitationSpans as never }}
      >
        {"Run `[Source 1]` in the shell.\n\n```\n[Source 2]\n```\n\nReal claim [Source 3]."}
      </ReactMarkdown>,
    );
    const chips = citationValues(document.body);
    expect(chips).toEqual(["3"]);
    expect(screen.getByText("[Source 1]")).toBeTruthy();
  });
});
