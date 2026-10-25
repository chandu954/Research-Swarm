import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CommandPalette from "@/components/CommandPalette";

function renderPalette(overrides: Partial<React.ComponentProps<typeof CommandPalette>> = {}) {
  const props = {
    open: true,
    onClose: vi.fn(),
    onNewChat: vi.fn(),
    onFocusComposer: vi.fn(),
    onOpenDocuments: vi.fn(),
    onOpenSettings: vi.fn(),
    ...overrides,
  };
  return { ...render(<CommandPalette {...props} />), props };
}

describe("CommandPalette", () => {
  it("filters actions and invokes the selected action with close", () => {
    const { props } = renderPalette();
    const search = screen.getByPlaceholderText("Search actions...");
    fireEvent.change(search, { target: { value: "upload" } });

    expect(screen.getByRole("button", { name: /upload documents/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /new research/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /upload documents/i }));

    expect(props.onOpenDocuments).toHaveBeenCalledOnce();
    expect(props.onClose).toHaveBeenCalledOnce();
  });

  it("runs the highlighted action on Enter and handles no matches and Escape", () => {
    const { props } = renderPalette();
    const search = screen.getByPlaceholderText("Search actions...");
    fireEvent.keyDown(search, { key: "ArrowDown" });
    fireEvent.keyDown(search, { key: "Enter" });
    expect(props.onFocusComposer).toHaveBeenCalledOnce();
    expect(props.onClose).toHaveBeenCalledOnce();

    fireEvent.change(search, { target: { value: "not an action" } });
    expect(screen.getByText(/no results for/i)).toBeInTheDocument();
    fireEvent.keyDown(search, { key: "Escape" });
    expect(props.onClose).toHaveBeenCalledTimes(2);
  });

  it("does not render while closed", () => {
    renderPalette({ open: false });
    expect(screen.queryByRole("dialog", { name: "Command palette" })).not.toBeInTheDocument();
  });
});
