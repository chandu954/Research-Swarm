"use client";

import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { api, API_URL, TOKEN_KEY, REFRESH_KEY, ApiClientError } from "./api-client";
import { clearSupabaseSession, storeSupabaseSession } from "./supabase/session";

interface TokenPair {
  access_token: string;
  refresh_token: string;
  supabase_access_token?: string | null;
  supabase_refresh_token?: string | null;
}

async function persistBridgeTokens(data: TokenPair) {
  if (data.supabase_access_token && data.supabase_refresh_token) {
    await storeSupabaseSession(data.supabase_access_token, data.supabase_refresh_token);
  }
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  avatar_url?: string | null;
  is_active: boolean;
  mfa_enabled: boolean;
}

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
  oauthLogin: (provider: "google" | "github" | "microsoft") => void;
  refreshToken: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | null>(null);

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function getStoredRefresh(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

function setCookie(name: string, value: string, days: number = 7) {
  if (typeof document === "undefined") return;
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/;${secure} SameSite=Lax`;
}

function removeCookie(name: string) {
  if (typeof document === "undefined") return;
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/;${secure} SameSite=Lax`;
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  removeCookie(TOKEN_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(getStoredToken);
  const [isLoading, setIsLoading] = useState(true);

  const setStoredToken = useCallback((t: string | null) => {
    setToken(t);
    if (t) {
      localStorage.setItem(TOKEN_KEY, t);
      setCookie(TOKEN_KEY, t);
    } else {
      clearAuth();
    }
  }, []);

  const fetchUser = useCallback(async () => {
    const t = getStoredToken();
    if (!t) { setIsLoading(false); return; }
    try {
      const data = await api.get<AuthUser>("/auth/me");
      setUser(data);
    } catch (e) {
      if (e instanceof ApiClientError && e.status === 401) {
        void clearSupabaseSession();
        clearAuth();
        setUser(null);
        setToken(null);
      }
    }
    setIsLoading(false);
  }, []);

  useEffect(() => { fetchUser(); }, [fetchUser]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.post<TokenPair>(
      "/auth/login",
      { email, password },
      { retryable: false },
    );
    setStoredToken(data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);
    await persistBridgeTokens(data);
    await fetchUser();
  }, [setStoredToken, fetchUser]);

  const register = useCallback(async (email: string, password: string, name: string) => {
    const data = await api.post<TokenPair>(
      "/auth/register",
      { email, password, name },
      { retryable: false },
    );
    setStoredToken(data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);
    await persistBridgeTokens(data);
    await fetchUser();
  }, [setStoredToken, fetchUser]);

  const logout = useCallback(() => {
    void clearSupabaseSession();
    clearAuth();
    setToken(null);
    setUser(null);
  }, []);

  const oauthLogin = useCallback(async (provider: "google" | "github" | "microsoft"): Promise<void> => {
    if (!window) return;
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.innerWidth - width) / 2;
    const top = window.screenY + (window.innerHeight - height) / 2;
    const popup = window.open(
      `${API_URL}/auth/${provider}`,
      `${provider}OAuth`,
      `width=${width},height=${height},left=${left},top=${top}`,
    );
    if (!popup) {
      // Popup blocked — fall back to redirect (full page navigation)
      window.location.href = `${API_URL}/auth/${provider}`;
      // Return a promise that never settles — page will navigate away
      return new Promise<never>(() => {});
    }
    return new Promise<void>((resolve, reject) => {
      const handler = (e: MessageEvent) => {
        if (e.origin !== API_URL && e.origin !== window.location.origin) return;
        if (e.data?.access_token) {
          setStoredToken(e.data.access_token);
          if (e.data.refresh_token) localStorage.setItem(REFRESH_KEY, e.data.refresh_token);
          if (e.data.supabase_access_token && e.data.supabase_refresh_token) {
            void persistBridgeTokens(e.data);
          }
          fetchUser();
          window.removeEventListener("message", handler);
          clearInterval(checkClosed);
          resolve();
        }
        if (e.data?.error) {
          window.removeEventListener("message", handler);
          clearInterval(checkClosed);
          reject(new Error(e.data.error));
        }
      };
      window.addEventListener("message", handler);
      const checkClosed = setInterval(() => {
        if (popup.closed) {
          clearInterval(checkClosed);
          window.removeEventListener("message", handler);
          reject(new DOMException("Popup closed", "AbortError"));
        }
      }, 500);
    });
  }, [setStoredToken, fetchUser]);

  const refreshToken = useCallback(async (): Promise<boolean> => {
    const rt = getStoredRefresh();
    if (!rt) return false;
    try {
      const data = await api.post<TokenPair>(
        "/auth/refresh",
        { refresh_token: rt },
        { retryable: false },
      );
      setStoredToken(data.access_token);
      if (data.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
      await persistBridgeTokens(data);
      return true;
    } catch {
      clearAuth();
      setToken(null);
      setUser(null);
      return false;
    }
  }, [setStoredToken]);

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout, oauthLogin, refreshToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
