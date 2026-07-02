import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import Chat from "@/components/Chat";
import type { Message } from "@/lib/types";

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

const mockMessages: Message[] = [
  { id: "1", role: "user", content: "Hello", timestamp: Date.now() },
  { id: "2", role: "assistant", content: "Hi there!", timestamp: Date.now() },
];

describe("Chat", () => {
  const baseProps = {
    messages: mockMessages,
    onSend: () => Promise.resolve(),
    isRunning: false,
    onOpenSettings: () => {},
    onOpenDocuments: () => {},
    onAttach: () => {},
    documents: [],
    providerSettings: {
      provider: "openrouter" as const,
      plannerModel: "qwen/qwen3-32b",
      researchModel: "google/gemini-2.5-pro",
      documentModel: "qwen/qwen3-32b",
      answerModel: "deepseek/deepseek-r1",
      openrouterKey: "",
    },
  };

  it("renders user message", () => {
    render(<Chat {...baseProps} />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("shows start research button when not running", () => {
    render(<Chat {...baseProps} />);
    expect(screen.getByRole("button", { name: /start research/i })).toBeInTheDocument();
  });

  it("shows running spinner when isRunning", () => {
    render(<Chat {...baseProps} isRunning={true} />);
    expect(screen.getByRole("button", { name: /research in progress/i })).toBeInTheDocument();
  });

  it("disables input when running", () => {
    render(<Chat {...baseProps} isRunning={true} />);
    const input = screen.getByRole("textbox", { name: /research question/i });
    expect(input).toBeDisabled();
  });
});
