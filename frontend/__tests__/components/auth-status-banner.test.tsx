import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import AuthStatusBanner from "@/components/auth/AuthStatusBanner";

describe("AuthStatusBanner", () => {
  it("renders checking banner with polite status", () => {
    render(<AuthStatusBanner banner={{ kind: "checking", message: "Connecting..." }} />);
    expect(screen.getByText("Connecting...")).toBeInTheDocument();
    const banner = screen.getByRole("status");
    expect(banner).toHaveAttribute("aria-live", "polite");
  });

  it("renders backend_offline banner with alert role", () => {
    render(<AuthStatusBanner banner={{ kind: "backend_offline", message: "Backend offline" }} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Backend offline")).toBeInTheDocument();
  });

  it("renders network_offline banner with alert role", () => {
    render(<AuthStatusBanner banner={{ kind: "network_offline", message: "Offline" }} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Offline")).toBeInTheDocument();
  });

  it("renders error banner with alert role", () => {
    render(<AuthStatusBanner banner={{ kind: "error", message: "Error occurred" }} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Error occurred")).toBeInTheDocument();
  });

  it("renders success banner with status role", () => {
    render(<AuthStatusBanner banner={{ kind: "success", message: "Success!" }} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText("Success!")).toBeInTheDocument();
  });

  it("renders session_expired banner with alert role", () => {
    render(<AuthStatusBanner banner={{ kind: "session_expired", message: "Session expired" }} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Session expired")).toBeInTheDocument();
  });
});
