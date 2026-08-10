/**
 * Centralized environment configuration for the Next.js frontend.
 *
 * Production builds FAIL LOUDLY when required configuration is missing —
 * they never silently fall back to localhost. Local development keeps a
 * convenient localhost default, and test runs keep the same default so
 * unit tests do not require environment variables.
 */

const LOCAL_API_BASE = "http://localhost:8000";
const LOCALHOST_MARKERS = ["localhost", "127.0.0.1"];

function stripTrailingSlashes(url: string): string {
  return url.replace(/\/+$/, "");
}

function assertNotLocalhost(value: string, name: string): void {
  if (LOCALHOST_MARKERS.some((marker) => value.includes(marker))) {
    throw new Error(
      `${name} must be the deployed production URL — it resolves to a local ` +
        `address (${value}). A production build must never point at localhost: ` +
        `local development values are only valid for local builds.`,
    );
  }
}

/**
 * Resolve the backend API base URL.
 *
 * - development / test: defaults to http://localhost:8000
 * - production: REQUIRES NEXT_PUBLIC_API_URL; throws a clear configuration
 *   error instead of shipping a bundle pointed at the visitor's own machine.
 */
export function getApiUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (configured) {
    const url = stripTrailingSlashes(configured);
    if (process.env.NODE_ENV === "production") assertNotLocalhost(url, "NEXT_PUBLIC_API_URL");
    return url;
  }
  if (process.env.NODE_ENV !== "production") return LOCAL_API_BASE;
  throw new Error(
    "NEXT_PUBLIC_API_URL is not configured. Set it in your Vercel project " +
      "(Production and Preview scopes) to the deployed backend URL, e.g. " +
      "https://research-swarm-api.up.railway.app",
  );
}

export interface SupabaseConfig {
  url: string;
  anonKey: string;
}

/**
 * Resolve the Supabase client configuration.
 *
 * Production and development both require real Supabase project values
 * (NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY). There is no
 * localhost default: a missing value raises a clear configuration error
 * rather than a confusing runtime crash inside the Supabase client.
 */
export function getSupabaseConfig(): SupabaseConfig {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    throw new Error(
      "NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY must be set — " +
        "create a Supabase project and configure these in your Vercel project " +
        "(Production and Preview scopes). Never use the service-role key here; " +
        "that stays server-side only.",
    );
  }
  if (process.env.NODE_ENV === "production") {
    assertNotLocalhost(url, "NEXT_PUBLIC_SUPABASE_URL");
  }
  return { url, anonKey };
}