"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  LogIn, Mail, Lock, Eye, EyeOff, User,
  BrainCircuit, AlertCircle, CheckCircle2,
  Loader2, Github, ArrowLeft, KeyRound, Send,
  ShieldCheck, ExternalLink,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { getErrorMessage, validateEmail, validatePassword, validateName } from "@/lib/errors";
import { api } from "@/lib/api-client";

type AuthView = "login" | "register" | "forgot-password" | "reset-password" | "check-email";

interface FieldErrors {
  email?: string;
  password?: string;
  name?: string;
  confirmPassword?: string;
}

const SOCIAL_PROVIDERS = [
  { id: "google" as const, label: "Google", icon: () => (
    <svg className="h-5 w-5" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
  ) },
  { id: "github" as const, label: "GitHub", icon: () => <Github className="h-5 w-5" /> },
  { id: "microsoft" as const, label: "Microsoft", icon: () => (
    <svg className="h-5 w-5" viewBox="0 0 24 24"><path fill="currentColor" d="M11.37 2h-9v9h9v-9zm0 11h-9v9h9v-9zm11-11h-9v9h9v-9zm0 11h-9v9h9v-9z"/></svg>
  ) },
];

export default function LoginPage() {
  const router = useRouter();
  const { login, register, oauthLogin } = useAuth();
  const [view, setView] = useState<AuthView>("login");
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [name, setName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [socialLoading, setSocialLoading] = useState<string | null>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const submitBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      setResetToken(token);
      setView("reset-password");
    }
  }, []);

  useEffect(() => { emailRef.current?.focus(); }, [view]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => { if (e.getModifierState("CapsLock")) setCapsLock(true); };
    const handleKeyUp = (e: KeyboardEvent) => { if (!e.getModifierState("CapsLock")) setCapsLock(false); };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => { window.removeEventListener("keydown", handleKeyDown); window.removeEventListener("keyup", handleKeyUp); };
  }, []);

  const clearErrors = useCallback(() => { setError(""); setFieldErrors({}); }, []);

  const validate = useCallback((): boolean => {
    const errors: FieldErrors = {};
    const emailErr = validateEmail(email);
    if (emailErr) errors.email = emailErr;

    if (view !== "forgot-password" && view !== "check-email") {
      const passErr = validatePassword(password);
      if (passErr) errors.password = passErr;
    }

    if (view === "register") {
      const nameErr = validateName(name);
      if (nameErr) errors.name = nameErr;
      if (confirmPassword && password !== confirmPassword) {
        errors.confirmPassword = "Passwords do not match";
      }
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }, [email, password, name, confirmPassword, view]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    clearErrors();
    if (!validate()) return;

    setLoading(true);
    try {
      if (view === "login") {
        await login(email.trim(), password);
        setSuccess(true);
        setTimeout(() => router.push("/app"), 300);
      } else if (view === "register") {
        await register(email.trim(), password, name.trim());
        setSuccess(true);
        setTimeout(() => router.push("/app"), 300);
      } else if (view === "forgot-password") {
        await api.post("/auth/forgot-password", { email: email.trim() }, { retryable: false });
        setView("check-email");
      } else if (view === "reset-password") {
        if (!resetToken) throw new Error("Missing reset token");
        await api.post("/auth/reset-password", { token: resetToken, password }, { retryable: false });
        setSuccess(true);
        setTimeout(() => {
          setView("login");
          setPassword("");
          setSuccess(false);
        }, 2000);
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err));
      if (submitBtnRef.current) submitBtnRef.current.focus();
    } finally {
      setLoading(false);
    }
  }, [view, email, password, name, resetToken, validate, clearErrors, login, register, router]);

  const handleSocialLogin = useCallback(async (provider: "google" | "github" | "microsoft") => {
    setSocialLoading(provider);
    setError("");
    try {
      oauthLogin(provider);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setSocialLoading(null);
    }
  }, [oauthLogin]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Escape") (e.currentTarget as HTMLElement).blur();
  }, []);

  const switchView = useCallback((newView: AuthView) => {
    setView(newView);
    clearErrors();
    setError("");
    setSuccess(false);
  }, [clearErrors]);

  const viewSubtitle = view === "login" ? "Welcome back to ResearchSwarm"
    : view === "register" ? "Start your research journey"
    : view === "forgot-password" ? "We'll send you a reset link"
    : view === "reset-password" ? "Enter your new password below"
    : "We sent a reset link to your email";

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#0a0a0f] p-4" role="main">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-40 -top-40 h-[500px] w-[500px] rounded-full bg-violet-500/5 blur-[120px]" />
        <div className="absolute -bottom-40 -right-40 h-[500px] w-[500px] rounded-full bg-cyan-500/5 blur-[120px]" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="relative w-full max-w-sm"
      >
        <div className="mb-8 text-center">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1, duration: 0.4 }}
            className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 shadow-lg shadow-violet-500/20"
            aria-hidden="true"
          >
            <BrainCircuit className="h-6 w-6 text-white" />
          </motion.div>
          <h1 className="text-xl font-semibold tracking-tight text-white">ResearchSwarm</h1>
          <p className="mt-1.5 text-sm text-gray-400">{viewSubtitle}</p>
        </div>

        <AnimatePresence mode="wait">
          {error && (
            <motion.div
              key="error"
              initial={{ opacity: 0, y: -8, height: 0 }}
              animate={{ opacity: 1, y: 0, height: "auto" }}
              exit={{ opacity: 0, y: -8, height: 0 }}
              transition={{ duration: 0.2 }}
              role="alert"
              aria-live="assertive"
              className="mb-4 flex items-start gap-2.5 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3.5 py-2.5"
            >
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-rose-400" />
              <span className="text-xs leading-5 text-rose-300">{error}</span>
            </motion.div>
          )}

          {success && (
            <motion.div
              key="success"
              initial={{ opacity: 0, y: -8, height: 0 }}
              animate={{ opacity: 1, y: 0, height: "auto" }}
              exit={{ opacity: 0, y: -8, height: 0 }}
              role="status"
              aria-live="polite"
              className="mb-4 flex items-center gap-2.5 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3.5 py-2.5"
            >
              <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 text-emerald-400" />
              <span className="text-xs text-emerald-300">Success! Redirecting...</span>
            </motion.div>
          )}
        </AnimatePresence>

        {view !== "check-email" && (
          <div className="mb-5 space-y-2.5">
            {SOCIAL_PROVIDERS.map((provider, i) => (
              <motion.button
                key={provider.id}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 + i * 0.05, duration: 0.3 }}
                onClick={() => handleSocialLogin(provider.id)}
                disabled={loading || socialLoading !== null}
                aria-label={`Continue with ${provider.label}`}
                className="group relative flex w-full items-center justify-center gap-3 overflow-hidden rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm font-medium text-gray-300 transition-all hover:border-white/[0.14] hover:bg-white/[0.06] hover:text-white disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {socialLoading === provider.id && (
                  <span className="absolute inset-0 flex items-center justify-center bg-white/[0.04] backdrop-blur-sm">
                    <Loader2 className="h-4 w-4 animate-spin text-gray-300" />
                  </span>
                )}
                <provider.icon />
                <span>Continue with {provider.label}</span>
              </motion.button>
            ))}
          </div>
        )}

        {view !== "check-email" && view !== "reset-password" && (
          <div className="relative mb-5" role="separator" aria-orientation="horizontal">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/[0.06]" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-[#0a0a0f] px-3 text-[11px] uppercase tracking-wider text-gray-500">
                Or {view === "forgot-password" ? "enter your email" : "continue with email"}
              </span>
            </div>
          </div>
        )}

        {view === "check-email" ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
            className="text-center"
          >
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/10">
              <Send className="h-6 w-6 text-emerald-400" />
            </div>
            <p className="text-sm text-gray-300">
              We sent a password reset link to
            </p>
            <p className="mt-1 text-sm font-medium text-white">{email}</p>
            <p className="mt-3 text-xs leading-5 text-gray-500">
              Didn&apos;t receive the email? Check your spam folder or{" "}
              <button
                type="button"
                onClick={() => { setView("forgot-password"); setError(""); }}
                className="font-medium text-violet-400 hover:text-violet-300 transition-colors"
              >
                try a different email
              </button>
            </p>
            <button
              type="button"
              onClick={() => switchView("login")}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-gray-400 transition-colors hover:border-white/[0.14] hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to sign in
            </button>
          </motion.div>
        ) : (
          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            {view === "register" && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
              >
                <label htmlFor="name" className="mb-1.5 block text-xs font-medium text-gray-400">
                  Full name <span className="text-rose-400">*</span>
                </label>
                <div className="relative">
                  <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                  <input
                    id="name"
                    type="text"
                    required
                    autoComplete="name"
                    value={name}
                    onChange={(e) => { setName(e.target.value); setFieldErrors(p => ({ ...p, name: undefined })); }}
                    onKeyDown={handleKeyDown}
                    aria-invalid={!!fieldErrors.name}
                    aria-describedby={fieldErrors.name ? "name-error" : undefined}
                    className="w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-3 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06] aria-[invalid=true]:border-rose-500/50"
                    placeholder="Your full name"
                  />
                </div>
                {fieldErrors.name && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} id="name-error" role="alert" className="mt-1 text-[11px] text-rose-400">{fieldErrors.name}</motion.p>
                )}
              </motion.div>
            )}

            {view === "reset-password" && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
              >
                <label className="mb-1.5 block text-xs font-medium text-gray-400">
                  Email address
                </label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                  <input
                    type="email"
                    value={email}
                    disabled
                    className="w-full rounded-xl border border-white/[0.08] bg-white/[0.02] py-2.5 pl-10 pr-3 text-sm text-gray-500 outline-none"
                    placeholder="you@example.com"
                  />
                </div>
              </motion.div>
            )}

            <div>
              <label htmlFor="email" className="mb-1.5 block text-xs font-medium text-gray-400">
                Email address <span className="text-rose-400">*</span>
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                <input
                  ref={emailRef}
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  inputMode="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setFieldErrors(p => ({ ...p, email: undefined })); }}
                  onKeyDown={handleKeyDown}
                  aria-invalid={!!fieldErrors.email}
                  aria-describedby={fieldErrors.email ? "email-error" : undefined}
                  className="w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-3 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06] aria-[invalid=true]:border-rose-500/50"
                  placeholder="you@example.com"
                />
              </div>
              {fieldErrors.email && (
                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} id="email-error" role="alert" className="mt-1 text-[11px] text-rose-400">{fieldErrors.email}</motion.p>
              )}
            </div>

            {view !== "forgot-password" && (
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
                    autoComplete={view === "login" ? "current-password" : "new-password"}
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setFieldErrors(p => ({ ...p, password: undefined })); }}
                    onKeyDown={handleKeyDown}
                    aria-invalid={!!fieldErrors.password}
                    aria-describedby={fieldErrors.password ? "password-error" : undefined}
                    className="w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-10 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06] aria-[invalid=true]:border-rose-500/50"
                    placeholder={view === "register" ? "Create a strong password" : "Enter your password"}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                    tabIndex={-1}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {fieldErrors.password && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} id="password-error" role="alert" className="mt-1 text-[11px] text-rose-400">{fieldErrors.password}</motion.p>
                )}
                {capsLock && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} role="alert" className="mt-1 text-[11px] text-amber-400">⚠ Caps Lock is on</motion.p>
                )}
                {(view === "register" || view === "reset-password") && password.length > 0 && (
                  <PasswordStrengthMeter password={password} />
                )}
              </div>
            )}

            {(view === "register" || view === "reset-password") && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
              >
                <label htmlFor="confirmPassword" className="mb-1.5 block text-xs font-medium text-gray-400">
                  Confirm password <span className="text-rose-400">*</span>
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                  <input
                    id="confirmPassword"
                    type={showPassword ? "text" : "password"}
                    required
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => { setConfirmPassword(e.target.value); setFieldErrors(p => ({ ...p, confirmPassword: undefined })); }}
                    onKeyDown={handleKeyDown}
                    aria-invalid={!!fieldErrors.confirmPassword}
                    className="w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-3 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06] aria-[invalid=true]:border-rose-500/50"
                    placeholder="Repeat your password"
                  />
                </div>
                {fieldErrors.confirmPassword && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} role="alert" className="mt-1 text-[11px] text-rose-400">{fieldErrors.confirmPassword}</motion.p>
                )}
              </motion.div>
            )}

            {view === "login" && (
              <div className="flex items-center justify-between">
                <label className="flex cursor-pointer items-center gap-2 text-xs text-gray-400 select-none">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="h-4 w-4 rounded border-white/[0.08] bg-white/[0.04] text-violet-500 focus:ring-violet-500/50 focus:ring-offset-0"
                  />
                  Remember me
                </label>
                <button
                  type="button"
                  onClick={() => switchView("forgot-password")}
                  className="text-xs font-medium text-violet-400 transition-colors hover:text-violet-300"
                >
                  Forgot password?
                </button>
              </div>
            )}

            {view === "forgot-password" && (
              <p className="text-[11px] leading-5 text-gray-500">
                Enter the email address associated with your account and we&apos;ll send you a link to reset your password.
              </p>
            )}

            <button
              ref={submitBtnRef}
              type="submit"
              disabled={loading}
              aria-busy={loading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-600 py-2.5 text-sm font-medium text-white shadow-lg shadow-violet-500/10 transition-all hover:opacity-90 hover:shadow-violet-500/20 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0a0f]"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  <span>
                    {view === "login" ? "Signing in..."
                      : view === "register" ? "Creating account..."
                      : view === "reset-password" ? "Resetting password..."
                      : "Sending reset link..."}
                  </span>
                </>
              ) : (
                <>
                  {view === "forgot-password" ? (
                    <Send className="h-4 w-4" aria-hidden="true" />
                  ) : view === "reset-password" ? (
                    <KeyRound className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <LogIn className="h-4 w-4" aria-hidden="true" />
                  )}
                  <span>
                    {view === "login" ? "Sign in"
                      : view === "register" ? "Create account"
                      : view === "reset-password" ? "Reset password"
                      : "Send reset link"}
                  </span>
                </>
              )}
            </button>
          </form>
        )}

        <div className="mt-6 text-center">
          {view === "login" && (
            <p className="text-xs text-gray-500">
              Don&apos;t have an account?{" "}
              <button
                type="button"
                onClick={() => switchView("register")}
                className="font-medium text-violet-400 transition-colors hover:text-violet-300"
              >
                Create one
              </button>
            </p>
          )}
          {view === "register" && (
            <p className="text-xs text-gray-500">
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => switchView("login")}
                className="font-medium text-violet-400 transition-colors hover:text-violet-300"
              >
                Sign in
              </button>
            </p>
          )}
          {(view === "forgot-password" || view === "reset-password") && (
            <button
              type="button"
              onClick={() => switchView("login")}
              className="inline-flex items-center gap-1.5 text-xs text-gray-500 transition-colors hover:text-gray-300"
            >
              <ArrowLeft className="h-3 w-3" />
              Back to sign in
            </button>
          )}
        </div>

        <div className="mt-8 text-center">
          <p className="text-[10px] text-gray-600">
            By continuing, you agree to our{" "}
            <a href="#" className="text-gray-500 underline underline-offset-2 hover:text-gray-300 transition-colors">Terms</a>
            {" "}and{" "}
            <a href="#" className="text-gray-500 underline underline-offset-2 hover:text-gray-300 transition-colors">Privacy Policy</a>
          </p>
          <div className="mt-3 flex items-center justify-center gap-3 text-[10px] text-gray-600">
            <span className="flex items-center gap-1">
              <ShieldCheck className="h-3 w-3" />
              Secure
            </span>
            <span className="h-3 w-px bg-white/[0.06]" />
            <span className="flex items-center gap-1">
              <KeyRound className="h-3 w-3" />
              Encrypted
            </span>
            <span className="h-3 w-px bg-white/[0.06]" />
            <span className="flex items-center gap-1">
              <ExternalLink className="h-3 w-3" />
              SOC2 Ready
            </span>
          </div>
        </div>
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

  const colors = ["bg-rose-500", "bg-orange-500", "bg-yellow-500", "bg-lime-500", "bg-emerald-500", "bg-emerald-400"];
  const labels = ["Very weak", "Weak", "Fair", "Good", "Strong", "Very strong"];

  return (
    <div className="mt-1.5" role="progressbar" aria-valuenow={Math.min(100, (score / 6) * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={`Password strength: ${labels[Math.min(score, 5)]}`}>
      <div className="flex gap-1">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className={`h-1 flex-1 rounded-full transition-colors ${i < score ? colors[i] : "bg-white/[0.08]"}`} />
        ))}
      </div>
      <p className="mt-0.5 text-[10px] text-gray-500">{labels[Math.min(score, 5)]}</p>
    </div>
  );
}
