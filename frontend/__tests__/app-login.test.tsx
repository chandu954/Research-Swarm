import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const authMocks = vi.hoisted(() => ({
  performLogin: vi.fn(), performRegister: vi.fn(), performOAuth: vi.fn(), dismissError: vi.fn(),
  state: { banner: null as unknown, isBlocked: false, isSubmitting: false, isOAuthLoading: (_provider: string) => false },
}));
vi.mock("@/lib/useLoginAuthFlow", () => ({ useLoginAuthFlow: () => ({
  ...authMocks.state,
  performLogin: authMocks.performLogin,
  performRegister: authMocks.performRegister,
  performOAuth: authMocks.performOAuth,
  dismissError: authMocks.dismissError,
}) }));
vi.mock("@/lib/api-client", () => ({ api: { post: vi.fn() } }));

import { api } from "@/lib/api-client";
import LoginPage from "@/app/login/page";

beforeEach(() => {
  vi.clearAllMocks();
  authMocks.state = { banner: null, isBlocked: false, isSubmitting: false, isOAuthLoading: () => false };
});

describe("LoginPage", () => {
  it("validates email and password before calling authentication", async () => {
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "bad-email" } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
    expect(authMocks.performLogin).not.toHaveBeenCalled();
  });

  it("trims email and calls login with the password as entered", async () => {
    authMocks.performLogin.mockResolvedValue(undefined);
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: " person@example.com " } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: "GoodPassword1!" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(authMocks.performLogin).toHaveBeenCalledWith("person@example.com", "GoodPassword1!"));
  });

  it("rejects registration with a mismatched confirmation and passes valid fields", async () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: /create one/i }));
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Ada Lovelace" } });
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "ada@example.com" } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: "StrongPassword1!" } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: "different" } });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText("Passwords do not match")).toBeInTheDocument();
    expect(authMocks.performRegister).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: "StrongPassword1!" } });
    authMocks.performRegister.mockResolvedValue(undefined);
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(authMocks.performRegister).toHaveBeenCalledWith(
      "ada@example.com", "StrongPassword1!", "Ada Lovelace",
    ));
  });

  it("submits forgot-password requests and shows the check-email state", async () => {
    vi.mocked(api.post).mockResolvedValue(undefined);
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: /forgot password/i }));
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: " person@example.com " } });
    fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(await screen.findByText("We sent a password reset link to")).toBeInTheDocument();
    expect(api.post).toHaveBeenCalledWith("/auth/forgot-password", { email: "person@example.com" }, { retryable: false });
  });

  it("shows reset API errors and reports success after a valid reset", async () => {
    window.history.replaceState({}, "", "/login?token=reset-token");
    vi.mocked(api.post).mockRejectedValueOnce(new Error("Reset token expired"));
    const { unmount } = render(<LoginPage />);
    fireEvent.change(await screen.findByLabelText(/email address/i), { target: { value: "ada@example.com" } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: "FreshPassword1!" } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: "FreshPassword1!" } });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Reset token expired");
    expect(api.post).toHaveBeenCalledWith("/auth/reset-password", {
      token: "reset-token", password: "FreshPassword1!",
    }, { retryable: false });
    unmount();

    vi.mocked(api.post).mockResolvedValueOnce(undefined);
    render(<LoginPage />);
    fireEvent.change(await screen.findByLabelText(/email address/i), { target: { value: "ada@example.com" } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: "FreshPassword1!" } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: "FreshPassword1!" } });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));
    expect(await screen.findByText(/password reset successful/i)).toBeInTheDocument();
  });
});
