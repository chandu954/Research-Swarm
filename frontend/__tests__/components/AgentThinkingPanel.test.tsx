import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import AgentThinkingPanel from "@/components/AgentThinkingPanel";
import type { AgentLog } from "@/lib/types";

vi.mock("@/lib/useElapsed", () => ({ useElapsed: () => 42 }));

vi.mock("framer-motion", async (importOriginal) => {
  const actual = await importOriginal<typeof import("framer-motion")>();
  return {
    ...actual,
    AnimatePresence: ({ children }: { children: ReactNode }) => children,
  };
});

vi.mock("@/components/AgentDAG", () => ({
  default: ({ onInspect }: { onInspect: (key: string) => void }) => (
    <button onClick={() => onInspect("planner")}>Inspect from graph</button>
  ),
}));

const logs: AgentLog[] = [
  { agent: "planner", action: "build_plan", status: "completed", timestamp: 1000, details: "Plan ready" },
  { agent: "planner", action: "refine_plan", status: "completed", timestamp: 2000 },
  { agent: "research_agent", action: "search_sources", status: "running", timestamp: 3000, details: "Searching sources" },
  { agent: "document_agent", action: "read_pdf", status: "failed", timestamp: 4000 },
];

describe("AgentThinkingPanel", () => {
  it("hides an idle panel until a run starts or completes an agent", () => {
    const { rerender } = render(<AgentThinkingPanel logs={[]} isRunning={false} />);
    expect(screen.queryByText("Research complete")).not.toBeInTheDocument();

    rerender(<AgentThinkingPanel logs={[]} isRunning />);
    expect(screen.getByText("AI agents working")).toBeInTheDocument();
    expect(screen.getByText("Coordinating agents...")).toBeInTheDocument();
    expect(screen.getByText("42s elapsed")).toBeInTheDocument();
  });

  it("shows agent states, progress, and expandable recent activity", () => {
    render(<AgentThinkingPanel logs={logs} isRunning />);
    expect(screen.getByText("1 of 4 agents complete")).toBeInTheDocument();
    expect(screen.getAllByText("Searching sources")).toHaveLength(2);
    expect(screen.getAllByText("refine plan")).toHaveLength(1);

    const inspectButton = screen.getByRole("button", { name: "Inspect Planner" });
    fireEvent.click(inspectButton.parentElement!.querySelectorAll("button")[1]);
    expect(screen.getByText("build plan")).toBeInTheDocument();
    expect(screen.getAllByText("refine plan")).toHaveLength(2);
  });

  it("switches between timeline and graph views and opens the agent inspector", async () => {
    render(<AgentThinkingPanel logs={logs} isRunning={false} />);
    expect(screen.getByText("Research complete")).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();

    const buttons = screen.getByText((_, element) => element?.textContent === "1 of 3 agents complete").parentElement!.querySelectorAll("button");
    fireEvent.click(buttons[1]);
    expect(screen.getAllByText("search sources").length).toBeGreaterThan(0);
    fireEvent.click(buttons[2]);
    fireEvent.click(screen.getByText("Inspect from graph"));
    expect(screen.getByRole("dialog", { name: "Agent Inspector: Planner" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close inspector" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
