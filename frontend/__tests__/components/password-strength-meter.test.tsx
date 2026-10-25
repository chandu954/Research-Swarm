import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import PasswordStrengthMeter from "@/components/auth/PasswordStrengthMeter";

describe("PasswordStrengthMeter", () => {
  it("renders very weak for empty password", () => {
    render(<PasswordStrengthMeter password="" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
    expect(screen.getByText("Very weak")).toBeInTheDocument();
  });

  it("renders weak for short password", () => {
    render(<PasswordStrengthMeter password="abc" />);
    const bar = screen.getByRole("progressbar");
    expect(Number(bar.getAttribute("aria-valuenow"))).toBeGreaterThan(0);
    expect(Number(bar.getAttribute("aria-valuenow"))).toBeLessThan(34);
  });

  it("renders fair for medium password with lowercase and digit", () => {
    render(<PasswordStrengthMeter password="abc123" />);
    const bar = screen.getByRole("progressbar");
    expect(Number(bar.getAttribute("aria-valuenow"))).toBeGreaterThanOrEqual(33);
    expect(Number(bar.getAttribute("aria-valuenow"))).toBeLessThan(67);
  });

  it("renders good for password with uppercase, lowercase, digit", () => {
    render(<PasswordStrengthMeter password="Abc12345" />);
    const bar = screen.getByRole("progressbar");
    expect(Number(bar.getAttribute("aria-valuenow"))).toBeGreaterThanOrEqual(50);
  });

  it("renders strong for password with special char", () => {
    render(<PasswordStrengthMeter password="Abc12345!" />);
    const bar = screen.getByRole("progressbar");
    expect(Number(bar.getAttribute("aria-valuenow"))).toBeGreaterThanOrEqual(67);
  });

  it("renders very strong for long password with all character classes", () => {
    render(<PasswordStrengthMeter password="Abc12345!xyz" />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
  });

  it("has accessibility attributes", () => {
    render(<PasswordStrengthMeter password="test1234" />);
    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-label")).toContain("Password strength");
  });
});
