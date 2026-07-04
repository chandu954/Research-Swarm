"use client";

import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { api, API_URL, TOKEN_KEY, REFRESH_KEY, ApiClientError } from "./api-client";

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
        clearAuth();
        setUser(null);
        setToken(null);
      }
    }
    setIsLoading(false);
  }, []);

  useEffect(() => { fetchUser(); }, [fetchUser]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.post<{ access_token: string; refresh_token: string }>(
      "/auth/login",
      { email, password },
      { retryable: false },
    );
    setStoredToken(data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);
    await fetchUser();
  }, [setStoredToken, fetchUser]);

  const register = useCallback(async (email: string, password: string, name: string) => {
    const data = await api.post<{ access_token: string; refresh_token: string }>(
      "/auth/register",
      { email, password, name },
      { retryable: false },
    );
    setStoredToken(data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);
    await fetchUser();
  }, [setStoredToken, fetchUser]);

  const logout = useCallback(() => {
    clearAuth();
    setToken(null);
    setUser(null);
  }, []);

  const oauthLogin = useCallback((provider: "google" | "github" | "microsoft") => {
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
      window.location.href = `${API_URL}/auth/${provider}`;
      return;
    }
    const handler = (e: MessageEvent) => {
      if (e.origin !== API_URL && e.origin !== window.location.origin) return;
      if (e.data?.access_token) {
        setStoredToken(e.data.access_token);
        localStorage.setItem(REFRESH_KEY, e.data.refresh_token);
        fetchUser();
        window.removeEventListener("message", handler);
      }
    };
    window.addEventListener("message", handler);
    const checkClosed = setInterval(() => {
      if (popup.closed) {
        clearInterval(checkClosed);
        window.removeEventListener("message", handler);
      }
    }, 500);
  }, [setStoredToken, fetchUser]);

  const refreshToken = useCallback(async (): Promise<boolean> => {
    const rt = getStoredRefresh();
    if (!rt) return false;
    try {
      const data = await api.post<{ access_token: string; refresh_token: string }>(
        "/auth/refresh",
        { refresh_token: rt },
        { retryable: false },
      );
      setStoredToken(data.access_token);
      if (data.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
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
