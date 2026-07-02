"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { LogIn, Mail, Lock, Eye, EyeOff, BrainCircuit, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
      const res = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `${mode === "login" ? "Login" : "Registration"} failed`);
      }

      const data = await res.json();
      localStorage.setItem("research-swarm-token", data.access_token);
      localStorage.setItem("research-swarm-refresh", data.refresh_token);
      router.push("/app");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0a0a0f] p-4">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-sm"
      >
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 shadow-lg">
            <BrainCircuit className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-xl font-semibold text-white">ResearchSwarm</h1>
          <p className="mt-1 text-sm text-gray-400">
            {mode === "login" ? "Sign in to your account" : "Create a new account"}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-300"
            >
              <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
              {error}
            </motion.div>
          )}

          <div>
            <label htmlFor="email" className="mb-1.5 block text-xs font-medium text-gray-400">
              Email
            </label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-3 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06]"
                placeholder="you@example.com"
              />
            </div>
          </div>

          <div>
            <label htmlFor="password" className="mb-1.5 block text-xs font-medium text-gray-400">
              Password
            </label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-10 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06]"
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-cyan-600 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {loading ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <LogIn className="h-4 w-4" />
            )}
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-gray-500">
          {mode === "login" ? (
            <>
              Don&apos;t have an account?{" "}
              <button
                type="button"
                onClick={() => { setMode("register"); setError(""); }}
                className="font-medium text-violet-400 hover:text-violet-300"
              >
                Register
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => { setMode("login"); setError(""); }}
                className="font-medium text-violet-400 hover:text-violet-300"
              >
                Sign in
              </button>
            </>
          )}
        </p>
      </motion.div>
    </div>
  );
}
