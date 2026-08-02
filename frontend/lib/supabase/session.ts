import { createClient } from "./client";

/**
 * Store the Supabase session minted by the FastAPI bridge.
 * createBrowserClient persists it to an `sb-<ref>-auth-token` cookie via
 * setSession, which the SSR server client and realtime both consume.
 */
export async function storeSupabaseSession(
  accessToken: string,
  refreshToken: string,
): Promise<boolean> {
  try {
    const supabase = createClient();
    const { error } = await supabase.auth.setSession({
      access_token: accessToken,
      refresh_token: refreshToken,
    });
    if (error) return false;
    return true;
  } catch {
    return false;
  }
}

export async function clearSupabaseSession(): Promise<void> {
  try {
    const supabase = createClient();
    await supabase.auth.signOut();
  } catch {
    // no-op — session may already be gone
  }
}

function readSbCookie(): { accessToken: string | null; refreshToken: string | null } {
  if (typeof document === "undefined") return { accessToken: null, refreshToken: null };
  for (const cookie of document.cookie.split("; ")) {
    const idx = cookie.indexOf("=");
    if (idx < 0) continue;
    const name = cookie.slice(0, idx);
    if (!name.startsWith("sb-") || !name.endsWith("-auth-token")) continue;
    const raw = decodeURIComponent(cookie.slice(idx + 1));
    // @supabase/ssr persists the session as `base64-<base64 JSON>`; also
    // tolerate a plain JSON payload for older/manual setups.
    try {
      const parsed = raw.startsWith("base64-")
        ? JSON.parse(atob(raw.slice("base64-".length)))
        : JSON.parse(raw);
      return {
        accessToken: parsed.access_token ?? null,
        refreshToken: parsed.refresh_token ?? null,
      };
    } catch {
      // not a session cookie — keep scanning
    }
  }
  return { accessToken: null, refreshToken: null };
}

/** Synchronous access-token read for API callers on the client. */
export function getSupabaseAccessToken(): string | null {
  return readSbCookie().accessToken;
}

export function hasSupabaseSession(): boolean {
  return readSbCookie().accessToken !== null;
}
