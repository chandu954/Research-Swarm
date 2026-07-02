"use client";

import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";

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
  refreshToken: () => Promise<void>;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_KEY = "research-swarm-token";
const REFRESH_KEY = "research-swarm-refresh";

const AuthContext = createContext<AuthContextType | null>(null);

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function getStoredRefresh(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(getStoredToken);
  const [isLoading, setIsLoading] = useState(true);

  const setStoredToken = useCallback((t: string | null) => {
    setToken(t);
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
  }, []);

  const fetchUser = useCallback(async () => {
    const t = getStoredToken();
    if (!t) { setIsLoading(false); return; }
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else {
        setStoredToken(null);
      }
    } catch { /* offline */ }
    setIsLoading(false);
  }, [setStoredToken]);

  useEffect(() => { fetchUser(); }, [fetchUser]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    setStoredToken(data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);
    await fetchUser();
  }, [setStoredToken, fetchUser]);

  const register = useCallback(async (email: string, password: string, name: string) => {
    const res = await fetch(`${API_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Registration failed");
    }
    const data = await res.json();
    setStoredToken(data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);
    await fetchUser();
  }, [setStoredToken, fetchUser]);

  const logout = useCallback(() => {
    setStoredToken(null);
    localStorage.removeItem(REFRESH_KEY);
    setUser(null);
  }, [setStoredToken]);

  const oauthLogin = useCallback((provider: "google" | "github" | "microsoft") => {
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.innerWidth - width) / 2;
    const top = window.screenY + (window.innerHeight - height) / 2;
    const popup = window.open(
      `${API_URL}/auth/${provider}`,
      `${provider}OAuth`,
      `width=${width},height=${height},left=${left},top=${top}`
    );
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
      if (popup?.closed) {
        clearInterval(checkClosed);
        window.removeEventListener("message", handler);
      }
    }, 500);
  }, [setStoredToken, fetchUser]);

  const refreshToken = useCallback(async () => {
    const rt = getStoredRefresh();
    if (!rt) return;
    try {
      const res = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (res.ok) {
        const data = await res.json();
        setStoredToken(data.access_token);
        localStorage.setItem(REFRESH_KEY, data.refresh_token);
      }
    } catch { /* ignore */ }
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
