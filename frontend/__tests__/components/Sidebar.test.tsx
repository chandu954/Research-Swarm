import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import Sidebar from "@/components/Sidebar";
import { AuthProvider } from "@/lib/auth";

beforeAll(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ conversations: [] }),
  });
});

describe("Sidebar", () => {
  const baseProps = {
    documents: [],
    recentQueries: [],
    onClearAll: vi.fn(),
    onNewChat: vi.fn(),
    onOpenDocuments: vi.fn(),
    onOpenSettings: vi.fn(),
  };

  const renderWithAuth = (ui: React.ReactElement) =>
    render(<AuthProvider>{ui}</AuthProvider>);

  it("renders sidebar with brand name", () => {
    renderWithAuth(<Sidebar {...baseProps} />);
    expect(screen.getByText("ResearchSwarm")).toBeInTheDocument();
  });

  it("shows new research button", () => {
    renderWithAuth(<Sidebar {...baseProps} />);
    expect(screen.getByText("New research")).toBeInTheDocument();
  });

  it("has navigation", () => {
    renderWithAuth(<Sidebar {...baseProps} />);
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });
});
