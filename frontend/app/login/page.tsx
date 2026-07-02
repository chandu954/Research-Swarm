"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  LogIn, Mail, Lock, Eye, EyeOff, User,
  BrainCircuit, AlertCircle, CheckCircle2,
  Loader2, Github, Monitor,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { getErrorMessage, validateEmail, validatePassword, validateName } from "@/lib/errors";

type AuthMode = "login" | "register";

interface FieldErrors {
  email?: string;
  password?: string;
  name?: string;
}

export default function LoginPage() {
  const router = useRouter();
  const { login, register, oauthLogin } = useAuth();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);
  const submitBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => { emailRef.current?.focus(); }, [mode]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.getModifierState("CapsLock")) setCapsLock(true);
    }
    function handleKeyUp(e: KeyboardEvent) {
      if (!e.getModifierState("CapsLock")) setCapsLock(false);
    }
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => { window.removeEventListener("keydown", handleKeyDown); window.removeEventListener("keyup", handleKeyUp); };
  }, []);

  const clearErrors = useCallback(() => { setError(""); setFieldErrors({}); }, []);

  function validate(): boolean {
    const errors: FieldErrors = {};
    const emailErr = validateEmail(email);
    if (emailErr) errors.email = emailErr;
    const passErr = validatePassword(password);
    if (passErr) errors.password = passErr;
    if (mode === "register") {
      const nameErr = validateName(name);
      if (nameErr) errors.name = nameErr;
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    clearErrors();
    if (!validate()) return;
    setLoading(true);
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await register(email.trim(), password, name.trim());
      }
      setSuccess(true);
      setTimeout(() => router.push("/app"), 300);
    } catch (err: any) {
      setError(getErrorMessage(err));
      if (submitBtnRef.current) submitBtnRef.current.focus();
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      (e.currentTarget as HTMLElement).blur();
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0a0a0f] p-4" role="main">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-sm"
      >
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 shadow-lg" aria-hidden="true">
            <BrainCircuit className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-xl font-semibold text-white">ResearchSwarm</h1>
          <p className="mt-1 text-sm text-gray-400">
            {mode === "login" ? "Sign in to your account" : "Create a new account"}
          </p>
        </div>

        <AnimatePresence mode="wait">
          {error && (
            <motion.div
              key="error"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              role="alert"
              aria-live="assertive"
              className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-2.5 text-xs text-rose-300"
            >
              <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5 self-start" />
              <span>{error}</span>
            </motion.div>
          )}

          {success && (
            <motion.div
              key="success"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              role="status"
              aria-live="polite"
              className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2.5 text-xs text-emerald-300"
            >
              <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0" />
              <span>Success! Redirecting...</span>
            </motion.div>
          )}
        </AnimatePresence>

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          {mode === "register" && (
            <div>
              <label htmlFor="name" className="mb-1.5 block text-xs font-medium text-gray-400">
                Name <span className="text-rose-400">*</span>
              </label>
              <div className="relative">
                <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                <input
                  ref={mode === "register" ? emailRef : undefined}
                  id="name"
                  type="text"
                  required
                  autoComplete="name"
                  value={name}
                  onChange={(e) => { setName(e.target.value); setFieldErrors(prev => ({ ...prev, name: undefined })); }}
                  onKeyDown={handleKeyDown}
                  aria-invalid={!!fieldErrors.name}
                  aria-describedby={fieldErrors.name ? "name-error" : undefined}
                  className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-3 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06] aria-[invalid=true]:border-rose-500/50"
                  placeholder="Your name"
                />
              </div>
              {fieldErrors.name && (
                <p id="name-error" role="alert" className="mt-1 text-[11px] text-rose-400">{fieldErrors.name}</p>
              )}
            </div>
          )}

          <div>
            <label htmlFor="email" className="mb-1.5 block text-xs font-medium text-gray-400">
              Email <span className="text-rose-400">*</span>
            </label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
              <input
                ref={mode === "login" ? emailRef : undefined}
                id="email"
                type="email"
                required
                autoComplete="email"
                inputMode="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setFieldErrors(prev => ({ ...prev, email: undefined })); }}
                onKeyDown={handleKeyDown}
                aria-invalid={!!fieldErrors.email}
                aria-describedby={fieldErrors.email ? "email-error" : undefined}
                className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-3 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06] aria-[invalid=true]:border-rose-500/50"
                placeholder="you@example.com"
              />
            </div>
            {fieldErrors.email && (
              <p id="email-error" role="alert" className="mt-1 text-[11px] text-rose-400">{fieldErrors.email}</p>
            )}
          </div>

          <div>
            <label htmlFor="password" className="mb-1.5 block text-xs font-medium text-gray-400">
              Password <span className="text-rose-400">*</span>
            </label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => { setPassword(e.target.value); setFieldErrors(prev => ({ ...prev, password: undefined })); }}
                onKeyDown={handleKeyDown}
                aria-invalid={!!fieldErrors.password}
                aria-describedby={fieldErrors.password ? "password-error" : undefined}
                className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-10 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06] aria-[invalid=true]:border-rose-500/50"
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                tabIndex={-1}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {fieldErrors.password && (
              <p id="password-error" role="alert" className="mt-1 text-[11px] text-rose-400">{fieldErrors.password}</p>
            )}
            {capsLock && (
              <p role="alert" className="mt-1 text-[11px] text-amber-400">⚠ Caps Lock is on</p>
            )}
            {mode === "register" && password.length > 0 && (
              <PasswordStrengthMeter password={password} />
            )}
          </div>

          {mode === "login" && (
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                <input type="checkbox" defaultChecked className="rounded border-white/[0.08] bg-white/[0.04] text-violet-500 focus:ring-violet-500/50" />
                Remember me
              </label>
              <button type="button" className="text-xs text-violet-400 hover:text-violet-300 transition-colors">
                Forgot password?
              </button>
            </div>
          )}

          <button
            ref={submitBtnRef}
            type="submit"
            disabled={loading}
            aria-busy={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-cyan-600 py-2.5 text-sm font-medium text-white transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0a0f]"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                <span>{mode === "login" ? "Signing in..." : "Creating account..."}</span>
              </>
            ) : (
              <>
                <LogIn className="h-4 w-4" aria-hidden="true" />
                <span>{mode === "login" ? "Sign in" : "Create account"}</span>
              </>
            )}
          </button>
        </form>

        <div className="relative my-6" role="separator" aria-orientation="horizontal">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-white/[0.06]" />
          </div>
          <div className="relative flex justify-center text-xs">
            <span className="bg-[#0a0a0f] px-2 text-gray-500">Or continue with</span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={() => oauthLogin("google")}
            aria-label="Sign in with Google"
            className="flex items-center justify-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-xs text-gray-300 transition-colors hover:bg-white/[0.08] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            <span className="hidden sm:inline">Google</span>
          </button>
          <button
            onClick={() => oauthLogin("github")}
            aria-label="Sign in with GitHub"
            className="flex items-center justify-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-xs text-gray-300 transition-colors hover:bg-white/[0.08] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50"
          >
            <Github className="h-4 w-4" aria-hidden="true" />
            <span className="hidden sm:inline">GitHub</span>
          </button>
          <button
            onClick={() => oauthLogin("microsoft")}
            aria-label="Sign in with Microsoft"
            className="flex items-center justify-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-xs text-gray-300 transition-colors hover:bg-white/[0.08] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50"
          >
            <Monitor className="h-4 w-4" aria-hidden="true" />
            <span className="hidden sm:inline">Microsoft</span>
          </button>
        </div>

        <p className="mt-6 text-center text-xs text-gray-500">
          {mode === "login" ? (
            <>Don&apos;t have an account?{" "}
              <button
                type="button"
                onClick={() => { setMode("register"); clearErrors(); }}
                className="font-medium text-violet-400 hover:text-violet-300 transition-colors focus-visible:outline-none focus-visible:underline"
              >
                Register
              </button>
            </>
          ) : (
            <>Already have an account?{" "}
              <button
                type="button"
                onClick={() => { setMode("login"); clearErrors(); }}
                className="font-medium text-violet-400 hover:text-violet-300 transition-colors focus-visible:outline-none focus-visible:underline"
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

function PasswordStrengthMeter({ password }: { password: string }) {
  const score =
    (password.length >= 8 ? 1 : 0) +
    (password.length >= 12 ? 1 : 0) +
    (/[A-Z]/.test(password) ? 1 : 0) +
    (/[a-z]/.test(password) ? 1 : 0) +
    (/[0-9]/.test(password) ? 1 : 0) +
    (/[^A-Za-z0-9]/.test(password) ? 1 : 0);

  const pct = Math.min(100, (score / 6) * 100);
  const colors = ["bg-rose-500", "bg-orange-500", "bg-yellow-500", "bg-lime-500", "bg-emerald-500", "bg-emerald-400"];
  const labels = ["Very weak", "Weak", "Fair", "Good", "Strong", "Very strong"];

  return (
    <div className="mt-1.5" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`Password strength: ${labels[Math.min(score, 5)]}`}>
      <div className="flex gap-1">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className={`h-1 flex-1 rounded-full transition-colors ${i < score ? colors[i] : "bg-white/[0.08]"}`} />
        ))}
      </div>
      <p className="mt-0.5 text-[10px] text-gray-500">{labels[Math.min(score, 5)]}</p>
    </div>
  );
}
