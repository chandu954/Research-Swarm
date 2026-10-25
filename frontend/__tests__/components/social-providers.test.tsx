import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SocialProviders from "@/components/auth/SocialProviders";

describe("SocialProviders", () => {
  it("renders Google provider button", () => {
    render(<SocialProviders disabled={false} isLoading={() => false} onSelect={vi.fn()} />);
    expect(screen.getByRole("button", { name: /continue with google/i })).toBeInTheDocument();
  });

  it("calls onSelect with provider id when clicked", () => {
    const onSelect = vi.fn();
    render(<SocialProviders disabled={false} isLoading={() => false} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /continue with google/i }));
    expect(onSelect).toHaveBeenCalledWith("google");
  });

  it("disables button when disabled prop is true", () => {
    render(<SocialProviders disabled={true} isLoading={() => false} onSelect={vi.fn()} />);
    const button = screen.getByRole("button", { name: /continue with google/i });
    expect(button).toBeDisabled();
  });

  it("shows loader when isLoading returns true", () => {
    render(<SocialProviders disabled={false} isLoading={() => true} onSelect={vi.fn()} />);
    const button = screen.getByRole("button", { name: /continue with google/i });
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("has aria-label for the provider button", () => {
    const onSelect = vi.fn();
    render(<SocialProviders disabled={false} isLoading={() => false} onSelect={onSelect} />);
    const button = screen.getByRole("button", { name: /continue with google/i });
    expect(button).toHaveAttribute("aria-label", "Continue with Google");
  });
});
