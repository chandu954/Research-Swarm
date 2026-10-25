import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const routeMocks = vi.hoisted(() => ({
  getReportById: vi.fn(),
  useParams: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useParams: routeMocks.useParams }));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));
vi.mock("@/lib/supabase/query", () => ({ getReportById: routeMocks.getReportById }));
vi.mock("@/components/ReportViewer", () => ({
  default: ({ report }: { report: { title: string } }) => <div>Rendered report: {report.title}</div>,
}));
vi.mock("@/components/Skeletons", () => ({
  ReportSkeleton: () => <div role="status">Loading report</div>,
}));

import ReportPage from "@/app/app/reports/[id]/page";

beforeEach(() => {
  vi.clearAllMocks();
  routeMocks.useParams.mockReturnValue({ id: "report-1" });
});

describe("ReportPage", () => {
  it("shows loading while the report request is pending and renders a ready report", async () => {
    let resolveReport!: (value: unknown) => void;
    routeMocks.getReportById.mockReturnValue(
      new Promise((resolve) => { resolveReport = resolve; }),
    );

    render(<ReportPage />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading report");

    await act(async () => resolveReport({ id: "report-1", status: "ready", title: "AI safety", content_md: "" }));

    expect(await screen.findByText("Rendered report: AI safety")).toBeInTheDocument();
    expect(routeMocks.getReportById).toHaveBeenCalledWith("report-1");
  });

  it.each([null, { id: "report-1", status: "processing", title: "Draft" }])(
    "renders the unavailable state for a missing or non-ready report",
    async (result) => {
      routeMocks.getReportById.mockResolvedValue(result);
      render(<ReportPage />);

      expect(await screen.findByRole("heading", { name: "Report not found" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /back to workspace/i })).toHaveAttribute("href", "/app");
    },
  );

  it("handles an absent route id without requesting a report", async () => {
    routeMocks.useParams.mockReturnValue({});
    render(<ReportPage />);

    expect(await screen.findByRole("heading", { name: "Report not found" })).toBeInTheDocument();
    expect(routeMocks.getReportById).not.toHaveBeenCalled();
  });

  it("ignores a response after the page unmounts", async () => {
    let resolveReport!: (value: unknown) => void;
    routeMocks.getReportById.mockReturnValue(new Promise((resolve) => { resolveReport = resolve; }));
    const { unmount } = render(<ReportPage />);
    unmount();

    await act(async () => resolveReport({ id: "report-1", status: "ready", title: "Late" }));
    expect(routeMocks.getReportById).toHaveBeenCalledTimes(1);
  });
});
