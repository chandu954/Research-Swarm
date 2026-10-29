"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LogIn, Mail, Lock, Eye, EyeOff, User,
  BrainCircuit, AlertCircle, CheckCircle2,
  Loader2, ArrowLeft, KeyRound, Send,
  ShieldCheck, ExternalLink,
} from "lucide-react";
import { getErrorMessage, validateEmail, validatePassword, validateName } from "@/lib/errors";
import { api } from "@/lib/api-client";
import { useLoginAuthFlow } from "@/lib/useLoginAuthFlow";
import type { AuthBanner } from "@/lib/auth-state-machine";
import AuthStatusBanner from "@/components/auth/AuthStatusBanner";
import PasswordStrengthMeter from "@/components/auth/PasswordStrengthMeter";
import SocialProviders from "@/components/auth/SocialProviders";

type AuthView = "login" | "register" | "forgot-password" | "reset-password" | "check-email";

interface FieldErrors {
  email?: string;
  password?: string;
  name?: string;
  passwordConfirmation?: string;
}

export default function LoginPage() {
  const {
    banner,
    isBlocked,
    isSubmitting,
    isOAuthLoading,
    performLogin,
    performRegister,
    performOAuth,
    dismissError,
  } = useLoginAuthFlow();

  const [view, setView] = useState<AuthView>("login");
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [name, setName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState("");
  const [operationSuccess, setOperationSuccess] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);
  const submitBtnRef = useRef<HTMLButtonElement>(null);

  const inputsDisabled = isBlocked || isSubmitting || formLoading;
  const authActionsDisabled = isBlocked || isSubmitting || formLoading;
  const submitBusy = isSubmitting || formLoading;

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
    const handleKeyDown = (e: KeyboardEvent) => { if (typeof e.getModifierState === "function" && e.getModifierState("CapsLock")) setCapsLock(true); };
    const handleKeyUp = (e: KeyboardEvent) => { if (typeof e.getModifierState === "function" && !e.getModifierState("CapsLock")) setCapsLock(false); };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => { window.removeEventListener("keydown", handleKeyDown); window.removeEventListener("keyup", handleKeyUp); };
  }, []);

  const clearFormErrors = useCallback(() => {
    setFormError("");
    setFieldErrors({});
    dismissError();
  }, [dismissError]);

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
      if (passwordConfirmation && password !== passwordConfirmation) {
        errors.passwordConfirmation = "Passwords do not match";
      }
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
    }, [email, password, name, passwordConfirmation, view]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (authActionsDisabled) return;
    clearFormErrors();
    if (!validate()) return;

    try {
      if (view === "login") {
        await performLogin(email.trim(), password);
      } else if (view === "register") {
        await performRegister(email.trim(), password, name.trim());
      } else if (view === "forgot-password") {
        setFormLoading(true);
        await api.post("/auth/forgot-password", { email: email.trim() }, { retryable: false });
        setView("check-email");
      } else if (view === "reset-password") {
        if (!resetToken) throw new Error("Missing reset token");
        setFormLoading(true);
        await api.post("/auth/reset-password", { token: resetToken, password }, { retryable: false });
        setOperationSuccess(true);
        setTimeout(() => {
          setView("login");
          setPassword("");
          setOperationSuccess(false);
        }, 2000);
      }
    } catch (err: unknown) {
      if (view === "login" || view === "register") {
        // Auth FSM handles banner; focus submit for accessibility
        submitBtnRef.current?.focus();
      } else {
        setFormError(getErrorMessage(err));
        submitBtnRef.current?.focus();
      }
    } finally {
      setFormLoading(false);
    }
  }, [view, email, password, name, resetToken, validate, clearFormErrors, performLogin, performRegister, authActionsDisabled]);

  const handleSocialLogin = useCallback(async (provider: "google") => {
    if (authActionsDisabled) return;
    clearFormErrors();
    await performOAuth(provider);
  }, [performOAuth, authActionsDisabled, clearFormErrors]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Escape") (e.currentTarget as HTMLElement).blur();
  }, []);

  const switchView = useCallback((newView: AuthView) => {
    setView(newView);
    clearFormErrors();
    setOperationSuccess(false);
  }, [clearFormErrors]);

  const viewSubtitle = view === "login" ? "Welcome back to ResearchSwarm"
    : view === "register" ? "Start your research journey"
    : view === "forgot-password" ? "We'll send you a reset link"
    : view === "reset-password" ? "Enter your new password below"
    : "We sent a reset link to your email";

  const showOperationSuccess = operationSuccess && view === "reset-password" && !banner;
  const showFormError = formError && !banner;

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
          {banner && <AuthStatusBanner banner={banner} />}
          {showFormError && (
            <motion.div
              key="form-error"
              initial={{ opacity: 0, y: -8, height: 0 }}
              animate={{ opacity: 1, y: 0, height: "auto" }}
              exit={{ opacity: 0, y: -8, height: 0 }}
              role="alert"
              aria-live="assertive"
              className="mb-4 flex items-start gap-2.5 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3.5 py-2.5"
            >
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-rose-400" />
              <span className="text-xs leading-5 text-rose-300">{formError}</span>
            </motion.div>
          )}
          {showOperationSuccess && (
            <motion.div
              key="operation-success"
              initial={{ opacity: 0, y: -8, height: 0 }}
              animate={{ opacity: 1, y: 0, height: "auto" }}
              exit={{ opacity: 0, y: -8, height: 0 }}
              role="status"
              aria-live="polite"
              className="mb-4 flex items-center gap-2.5 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3.5 py-2.5"
            >
              <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 text-emerald-400" />
              <span className="text-xs text-emerald-300">Password reset successful. Returning to sign in...</span>
            </motion.div>
          )}
        </AnimatePresence>

        {view !== "check-email" && (
          <SocialProviders
            disabled={authActionsDisabled}
            isLoading={isOAuthLoading}
            onSelect={handleSocialLogin}
          />
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
            <p className="text-sm text-gray-300">We sent a password reset link to</p>
            <p className="mt-1 text-sm font-medium text-white">{email}</p>
            <p className="mt-3 text-xs leading-5 text-gray-500">
              Didn&apos;t receive the email? Check your spam folder or{" "}
              <button
                type="button"
                onClick={() => { setView("forgot-password"); setFormError(""); }}
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
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
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
                    disabled={inputsDisabled}
                    value={name}
                    onChange={(e) => { setName(e.target.value); setFieldErrors(p => ({ ...p, name: undefined })); }}
                    onKeyDown={handleKeyDown}
                    aria-invalid={!!fieldErrors.name}
                    className="w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-3 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06] disabled:opacity-50 disabled:cursor-not-allowed"
                    placeholder="Your full name"
                  />
                </div>
                {fieldErrors.name && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} role="alert" className="mt-1 text-[11px] text-rose-400">{fieldErrors.name}</motion.p>
                )}
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
                  disabled={inputsDisabled}
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setFieldErrors(p => ({ ...p, email: undefined })); }}
                  onKeyDown={handleKeyDown}
                  aria-invalid={!!fieldErrors.email}
                  className="w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-3 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06] disabled:opacity-50 disabled:cursor-not-allowed"
                  placeholder="you@example.com"
                />
              </div>
              {fieldErrors.email && (
                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} role="alert" className="mt-1 text-[11px] text-rose-400">{fieldErrors.email}</motion.p>
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
                    disabled={inputsDisabled}
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setFieldErrors(p => ({ ...p, password: undefined })); }}
                    onKeyDown={handleKeyDown}
                    aria-invalid={!!fieldErrors.password}
                    className="w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-10 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06] disabled:opacity-50 disabled:cursor-not-allowed"
                    placeholder={view === "register" ? "Create a strong password" : "Enter your password"}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    disabled={inputsDisabled}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors disabled:opacity-50"
                    tabIndex={-1}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {fieldErrors.password && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} role="alert" className="mt-1 text-[11px] text-rose-400">{fieldErrors.password}</motion.p>
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
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}>
                <label htmlFor="passwordConfirmation" className="mb-1.5 block text-xs font-medium text-gray-400">
                  Confirm password <span className="text-rose-400">*</span>
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                  <input
                     id="passwordConfirmation"
                    type={showPassword ? "text" : "password"}
                    required
                    autoComplete="new-password"
                    disabled={inputsDisabled}
                    value={passwordConfirmation}
                    onChange={(e) => { setPasswordConfirmation(e.target.value); setFieldErrors(p => ({ ...p, passwordConfirmation: undefined })); }}
                    onKeyDown={handleKeyDown}
                    className="w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-3 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06] disabled:opacity-50 disabled:cursor-not-allowed"
                    placeholder="Repeat your password"
                  />
                </div>
                {fieldErrors.passwordConfirmation && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} role="alert" className="mt-1 text-[11px] text-rose-400">{fieldErrors.passwordConfirmation}</motion.p>
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
                    disabled={inputsDisabled}
                    className="h-4 w-4 rounded border-white/[0.08] bg-white/[0.04] text-violet-500 focus:ring-violet-500/50 focus:ring-offset-0 disabled:opacity-50"
                  />
                  Remember me
                </label>
                <button
                  type="button"
                  onClick={() => switchView("forgot-password")}
                  disabled={inputsDisabled}
                  className="text-xs font-medium text-violet-400 transition-colors hover:text-violet-300 disabled:opacity-50"
                >
                  Forgot password?
                </button>
              </div>
            )}

            <button
              ref={submitBtnRef}
              type="submit"
              disabled={authActionsDisabled}
              aria-busy={submitBusy}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-600 py-2.5 text-sm font-medium text-white shadow-lg shadow-violet-500/10 transition-all hover:opacity-90 hover:shadow-violet-500/20 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0a0f]"
            >
              {submitBusy ? (
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
                  {view === "forgot-password" ? <Send className="h-4 w-4" aria-hidden="true" />
                    : view === "reset-password" ? <KeyRound className="h-4 w-4" aria-hidden="true" />
                    : <LogIn className="h-4 w-4" aria-hidden="true" />}
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
              <button type="button" onClick={() => switchView("register")} disabled={inputsDisabled} className="font-medium text-violet-400 transition-colors hover:text-violet-300 disabled:opacity-50">
                Create one
              </button>
            </p>
          )}
          {view === "register" && (
            <p className="text-xs text-gray-500">
              Already have an account?{" "}
              <button type="button" onClick={() => switchView("login")} disabled={inputsDisabled} className="font-medium text-violet-400 transition-colors hover:text-violet-300 disabled:opacity-50">
                Sign in
              </button>
            </p>
          )}
          {(view === "forgot-password" || view === "reset-password") && (
            <button type="button" onClick={() => switchView("login")} disabled={inputsDisabled} className="inline-flex items-center gap-1.5 text-xs text-gray-500 transition-colors hover:text-gray-300 disabled:opacity-50">
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
        </div>
      </motion.div>
    </div>
  );
}
