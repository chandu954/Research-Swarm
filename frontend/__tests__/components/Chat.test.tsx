import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import Chat from "@/components/Chat";
import type { Message } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: null,
    token: null,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    oauthLogin: vi.fn(),
    refreshToken: vi.fn(),
  }),
}));

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

  it("renders failure card with human reason when runError is set", () => {
    render(<Chat {...baseProps} runError="The backend may be offline. Check your connection and try again." />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Research failed")).toBeInTheDocument();
    expect(
      screen.getByText("The backend may be offline. Check your connection and try again.")
    ).toBeInTheDocument();
  });

  it("exposes a retry button when onRetry is provided", () => {
    const onRetry = vi.fn();
    render(<Chat {...baseProps} runError="boom" onRetry={onRetry} />);
    const retry = screen.getByRole("button", { name: /retry research/i });
    expect(retry).toBeInTheDocument();
    retry.click();
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("does not render the failure card while a new run is in flight", () => {
    render(<Chat {...baseProps} runError="boom" isRunning={true} onRetry={() => {}} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not render the failure card when there is no error", () => {
    render(<Chat {...baseProps} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows the cancelled state as an idle assistant message, not an alert", () => {
    const cancelled: Message[] = [
      { id: "1", role: "user", content: "Hello", timestamp: Date.now() },
      {
        id: "2",
        role: "assistant",
        content: "**Research cancelled.** The workspace is idle and ready for a new query.",
        timestamp: Date.now(),
      },
      { id: "3", role: "assistant", content: "Trailing", timestamp: Date.now() },
    ];
    render(<Chat {...baseProps} messages={cancelled} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.getByText((content) => /Research cancelled\./.test(content))
    ).toBeInTheDocument();
  });
});
