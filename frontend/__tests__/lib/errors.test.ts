import { describe, expect, it } from "vitest";
import {
  getErrorMessage,
  parseError,
  parseResponseError,
  validateEmail,
  validateName,
  validatePassword,
} from "@/lib/errors";

describe("parseError", () => {
  it("handles falsy error", () => {
    expect(parseError(null)).toEqual({
      message: "Something went wrong. Please try again.",
    });
    expect(parseError(undefined)).toEqual({
      message: "Something went wrong. Please try again.",
    });
  });

  it("handles TypeError network/fetch errors", () => {
    const result = parseError(new TypeError("Failed to fetch"));
    expect(result.code).toBe("NETWORK_ERROR");
    expect(result.message).toContain("Unable to reach the server");
  });

  it("handles TypeError with friendly message", () => {
    const result = parseError(new TypeError("invalid credentials"));
    expect(result.code).toBe("NETWORK_ERROR");
    expect(result.message).toBe("Incorrect email or password.");
  });

  it("handles AbortError DOMException", () => {
    const err = new DOMException("aborted", "AbortError");
    expect(parseError(err)).toEqual({
      message: "Request was cancelled.",
      code: "ABORTED",
    });
  });

  it("handles generic Error with message", () => {
    const err = new Error("invalid credentials");
    expect(parseError(err)).toEqual({
      message: "Incorrect email or password.",
      status: undefined,
    });
  });

  it("handles string error", () => {
    expect(parseError("network error")).toEqual({
      message: "Unable to reach the server. Check your connection.",
    });
  });

  it("handles object with response.data.message", () => {
    const err = {
      response: { data: { message: "invalid email" }, status: 400 },
    };
    expect(parseError(err)).toEqual({
      message: "Please enter a valid email address.",
      status: 400,
    });
  });

  it("handles object with response.data.detail", () => {
    const err = { response: { data: { detail: "not found" }, status: 404 } };
    expect(parseError(err)).toEqual({
      message: "The requested resource was not found.",
      status: 404,
    });
  });

  it("handles object with response.data.error", () => {
    const err = { response: { data: { error: "forbidden" }, status: 403 } };
    expect(parseError(err)).toEqual({
      message: "You do not have permission to perform this action.",
      status: 403,
    });
  });

  it("handles object with response.status only", () => {
    const err = {
      response: { status: 500, statusText: "internal server error" },
    };
    expect(parseError(err)).toEqual({
      message: "Something went wrong on our end. Please try again.",
      status: 500,
    });
  });

  it("handles object with data.message", () => {
    const err = { data: { message: "rate limit" } };
    expect(parseError(err)).toEqual({
      message: "Too many requests. Please wait a moment and try again.",
    });
  });

  it("handles object with data.detail", () => {
    const err = { data: { detail: "email already registered" } };
    expect(parseError(err)).toEqual({
      message: "This email is already registered.",
    });
  });

  it("handles object with data.error", () => {
    const err = { data: { error: "too many" } };
    expect(parseError(err)).toEqual({
      message: "Too many attempts. Please wait a few minutes before trying again.",
    });
  });

  it("handles object with message property", () => {
    const err = { message: "invalid credentials", status: 401 };
    expect(parseError(err)).toEqual({
      message: "Incorrect email or password.",
      status: 401,
    });
  });

  it("handles object with detail property", () => {
    const err = { detail: "email already registered", status: 409 };
    expect(parseError(err)).toEqual({
      message: "This email is already registered.",
      status: 409,
    });
  });

  it("handles object with error property", () => {
    const err = { error: "forbidden" };
    expect(parseError(err)).toEqual({
      message: "You do not have permission to perform this action.",
    });
  });

  it("handles object with statusText only", () => {
    const err = { statusText: "not found", status: 404 };
    expect(parseError(err)).toEqual({
      message: "The requested resource was not found.",
      status: 404,
    });
  });

  it("handles object with code", () => {
    const err = { code: "organization_required" };
    expect(parseError(err)).toEqual({
      message: "We need to set up your workspace before you can start researching.",
      code: "organization_required",
    });
  });

  it("falls back to generic message for unrecognized objects", () => {
    expect(parseError({ foo: "bar" })).toEqual({
      message: "Something went wrong. Please try again.",
    });
  });
});

describe("parseResponseError", () => {
  it("parses JSON body with detail", async () => {
    const res = {
      status: 400,
      json: () => Promise.resolve({ detail: "invalid email" }),
      text: () => Promise.resolve(""),
    } as Response;
    expect(await parseResponseError(res)).toEqual({
      message: "Please enter a valid email address.",
      status: 400,
    });
  });

  it("parses JSON body with message", async () => {
    const res = {
      status: 422,
      json: () => Promise.resolve({ message: "check your input" }),
      text: () => Promise.resolve(""),
    } as Response;
    expect(await parseResponseError(res)).toEqual({
      message: "check your input",
      status: 422,
    });
  });

  it("handles invalid JSON body", async () => {
    const res = {
      status: 500,
      json: () => Promise.reject(new Error("not json")),
      text: () => Promise.resolve("server error"),
    } as Response;
    expect(await parseResponseError(res)).toEqual({
      message: "server error",
      status: 500,
    });
  });

  it("returns status text for empty body", async () => {
    const res = {
      status: 503,
      json: () => Promise.reject(new Error("not json")),
      text: () => Promise.resolve(""),
    } as Response;
    expect(await parseResponseError(res)).toEqual({
      message: "The server is temporarily unavailable. Please try again.",
      status: 503,
    });
  });
});

describe("getErrorMessage", () => {
  it("handles strings", () => {
    expect(getErrorMessage("invalid email")).toBe(
      "Please enter a valid email address.",
    );
  });

  it("handles Error instances", () => {
    expect(getErrorMessage(new Error("invalid credentials"))).toBe(
      "Incorrect email or password.",
    );
    expect(getErrorMessage(new Error("[object Object]"))).toBe(
      "Something went wrong. Please try again.",
    );
  });

  it("handles objects via parseError", () => {
    expect(
      getErrorMessage({ response: { data: { message: "rate limit" } } }),
    ).toBe("Too many requests. Please wait a moment and try again.");
  });
});

describe("validateEmail", () => {
  it("rejects empty email", () => {
    expect(validateEmail("")).toBe("Email is required.");
    expect(validateEmail("   ")).toBe("Email is required.");
  });

  it("rejects invalid email", () => {
    expect(validateEmail("not-an-email")).toBe(
      "Please enter a valid email address.",
    );
    expect(validateEmail("noatsign.com")).toBe(
      "Please enter a valid email address.",
    );
  });

  it("accepts valid email", () => {
    expect(validateEmail("user@example.com")).toBeNull();
  });
});

describe("validatePassword", () => {
  it("rejects empty password", () => {
    expect(validatePassword("")).toBe("Password is required.");
  });

  it("rejects short password", () => {
    expect(validatePassword("short")).toBe(
      "Password must be at least 8 characters.",
    );
  });

  it("rejects overlong password", () => {
    expect(validatePassword("a".repeat(129))).toBe(
      "Password must be under 128 characters.",
    );
  });

  it("accepts valid password", () => {
    expect(validatePassword("securepass123")).toBeNull();
  });
});

describe("validateName", () => {
  it("rejects empty name", () => {
    expect(validateName("")).toBe("Name is required.");
    expect(validateName("   ")).toBe("Name is required.");
  });

  it("rejects overlong name", () => {
    expect(validateName("a".repeat(256))).toBe(
      "Name must be under 255 characters.",
    );
  });

  it("accepts valid name", () => {
    expect(validateName("John Doe")).toBeNull();
  });
});
