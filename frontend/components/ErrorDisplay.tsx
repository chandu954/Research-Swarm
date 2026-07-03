"use client";

import { motion } from "framer-motion";
import {
  AlertCircle, WifiOff, Clock, ShieldAlert,
  ServerCrash, RefreshCw, ExternalLink, Ban,
} from "lucide-react";
import { ApiClientError } from "@/lib/api-client";

interface ErrorDisplayProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
  variant?: "inline" | "fullscreen" | "toast";
}

const ERROR_ICONS: Record<string, typeof AlertCircle> = {
  OFFLINE: WifiOff,
  TIMEOUT: Clock,
  UNAUTHORIZED: ShieldAlert,
  FORBIDDEN: Ban,
  RATE_LIMITED: Clock,
  ORGANIZATION_REQUIRED: AlertCircle,
  INTERNAL_ERROR: ServerCrash,
  UNKNOWN: AlertCircle,
};

const ERROR_ACTIONS: Record<string, { label: string; action: string }> = {
  OFFLINE:            { label: "Check connection", action: "diagnose" },
  TIMEOUT:            { label: "Try again", action: "retry" },
  UNAUTHORIZED:       { label: "Sign in", action: "login" },
  FORBIDDEN:          { label: "Contact support", action: "support" },
  ORGANIZATION_REQUIRED: { label: "Set up workspace", action: "onboarding" },
  INTERNAL_ERROR:     { label: "Try again", action: "retry" },
  RATE_LIMITED:       { label: "Wait and retry", action: "retry" },
  UNKNOWN:            { label: "Try again", action: "retry" },
};

function parseError(error: unknown): { code: string; message: string; status: number } {
  if (error instanceof ApiClientError) {
    return { code: error.code, message: error.message, status: error.status };
  }
  if (error instanceof TypeError) {
    if (error.message.includes("fetch") || error.message.includes("network")) {
      return { code: "OFFLINE", message: "We couldn't reach the ResearchSwarm server. Check your internet connection.", status: 0 };
    }
    return { code: "UNKNOWN", message: error.message, status: 0 };
  }
  return { code: "UNKNOWN", message: "An unexpected error occurred. Please try again.", status: 0 };
}

export function ErrorDisplay({ error, onRetry, title, variant = "inline" }: ErrorDisplayProps) {
  const { code, message } = parseError(error);
  const Icon = ERROR_ICONS[code] || AlertCircle;
  const action = ERROR_ACTIONS[code] || { label: "Try again", action: "retry" };

  const handleAction = () => {
    if (action.action === "retry" && onRetry) onRetry();
    else if (action.action === "onboarding") window.location.href = "/onboarding";
    else if (action.action === "login") window.location.href = "/login";
  };

  if (variant === "fullscreen") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0f] p-4">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-sm text-center"
        >
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-rose-400/20 bg-rose-500/10 text-rose-300">
            <Icon className="h-6 w-6" />
          </span>
          <h2 className="mt-5 text-lg font-semibold text-white">{title || "Something went wrong"}</h2>
          <p className="mt-2 text-sm leading-6 text-gray-400">{message}</p>
          <div className="mt-6 flex flex-col items-center gap-3">
            {onRetry && (
              <button
                onClick={onRetry}
                className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-cyan-600 px-5 py-2.5 text-sm font-medium text-white transition-all hover:opacity-90"
              >
                <RefreshCw className="h-4 w-4" />
                {action.label}
              </button>
            )}
            <button
              onClick={handleAction}
              className="flex items-center gap-2 rounded-lg border border-white/[0.08] px-4 py-2 text-xs text-gray-400 transition-colors hover:text-gray-200"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              {action.label}
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-start gap-3 rounded-lg border border-rose-500/20 bg-rose-500/5 px-4 py-3"
    >
      <Icon className="mt-0.5 h-4 w-4 flex-shrink-0 text-rose-400" />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-rose-300">{title || "Error"}</p>
        <p className="mt-0.5 text-xs text-rose-400/80">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1 rounded-md border border-rose-500/20 px-2.5 py-1.5 text-xs text-rose-300 transition-colors hover:bg-rose-500/10"
        >
          <RefreshCw className="h-3 w-3" />
          Retry
        </button>
      )}
    </motion.div>
  );
}
