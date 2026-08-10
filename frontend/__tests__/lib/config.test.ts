import { describe, it, expect, vi, afterEach } from "vitest";
import { getApiUrl, getSupabaseConfig } from "@/lib/config";

describe("getApiUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("uses the configured NEXT_PUBLIC_API_URL", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com");
    expect(getApiUrl()).toBe("https://api.example.com");
  });

  it("strips trailing slashes so websocket/endpoint joins stay clean", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com/");
    expect(getApiUrl()).toBe("https://api.example.com");
  });

  it("falls back to localhost during development", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NODE_ENV", "development");
    expect(getApiUrl()).toBe("http://localhost:8000");
  });

  it("throws a clear configuration error in production without the env var", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NODE_ENV", "production");
    expect(() => getApiUrl()).toThrow(/NEXT_PUBLIC_API_URL is not configured/);
  });

  it("never falls back to localhost in production", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com");
    vi.stubEnv("NODE_ENV", "production");
    expect(getApiUrl().includes("localhost")).toBe(false);
  });

  it("rejects localhost values in production builds", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
    vi.stubEnv("NODE_ENV", "production");
    expect(() => getApiUrl()).toThrow(/must be the deployed production URL/);
  });

  it("allows localhost values during development", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
    vi.stubEnv("NODE_ENV", "development");
    expect(getApiUrl()).toBe("http://localhost:8000");
  });
});

describe("getSupabaseConfig", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("returns url and anon key when both are set", () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://proj.supabase.co");
    vi.stubEnv(
      "NEXT_PUBLIC_SUPABASE_ANON_KEY",
      "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.anon",
    );
    const config = getSupabaseConfig();
    expect(config.url).toBe("https://proj.supabase.co");
    expect(config.anonKey).toContain("anon");
  });

  it("throws a clear error when either value is missing", () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "");
    expect(() => getSupabaseConfig()).toThrow(/NEXT_PUBLIC_SUPABASE_URL/);
  });

  it("throws a clear error when only the URL is set", () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://proj.supabase.co");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "");
    expect(() => getSupabaseConfig()).toThrow(/NEXT_PUBLIC_SUPABASE_ANON_KEY/);
  });

  it("rejects the local Supabase URL in production builds", () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://127.0.0.1:54321");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
    vi.stubEnv("NODE_ENV", "production");
    expect(() => getSupabaseConfig()).toThrow(/must be the deployed production URL/);
  });

  it("allows the local Supabase URL during development", () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://127.0.0.1:54321");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
    vi.stubEnv("NODE_ENV", "development");
    const config = getSupabaseConfig();
    expect(config.url).toBe("http://127.0.0.1:54321");
  });
});