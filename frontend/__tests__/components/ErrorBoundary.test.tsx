import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ErrorBoundary from "@/components/ErrorBoundary";

const logError = vi.hoisted(() => vi.fn());
vi.mock("@/lib/logger", () => ({ logger: { error: logError } }));

function Broken({ fail }: { fail: boolean }) {
  if (fail) throw new Error("render failed");
  return <p>Working content</p>;
}

beforeEach(() => {
  logError.mockClear();
});

describe("ErrorBoundary", () => {
  it("logs render errors, calls onError, and recovers when retried", () => {
    const onError = vi.fn();
    const { rerender } = render(
      <ErrorBoundary onError={onError}><Broken fail /></ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("render failed")).toBeInTheDocument();
    expect(logError).toHaveBeenCalledWith("Uncaught render error", expect.objectContaining({
      error: expect.objectContaining({ message: "render failed" }),
    }));
    expect(onError).toHaveBeenCalledTimes(1);

    rerender(<ErrorBoundary onError={onError}><Broken fail={false} /></ErrorBoundary>);
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(screen.getByText("Working content")).toBeInTheDocument();
  });

  it("renders a supplied fallback instead of the default error UI", () => {
    render(<ErrorBoundary fallback={<p>Custom failure UI</p>}><Broken fail /></ErrorBoundary>);
    expect(screen.getByText("Custom failure UI")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });
});
