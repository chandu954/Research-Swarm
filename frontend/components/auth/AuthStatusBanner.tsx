"use client";

import { motion } from "framer-motion";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

import type { AuthBanner } from "@/lib/auth-state-machine";

const STYLES: Record<
  AuthBanner["kind"],
  { border: string; bg: string; text: string; icon: string }
> = {
  checking: {
    border: "border-white/[0.06]",
    bg: "bg-white/[0.03]",
    text: "text-gray-400",
    icon: "text-gray-400",
  },
  backend_offline: {
    border: "border-amber-500/20",
    bg: "bg-amber-500/10",
    text: "text-amber-300",
    icon: "text-amber-400",
  },
  network_offline: {
    border: "border-amber-500/20",
    bg: "bg-amber-500/10",
    text: "text-amber-300",
    icon: "text-amber-400",
  },
  error: {
    border: "border-rose-500/20",
    bg: "bg-rose-500/10",
    text: "text-rose-300",
    icon: "text-rose-400",
  },
  success: {
    border: "border-emerald-500/20",
    bg: "bg-emerald-500/10",
    text: "text-emerald-300",
    icon: "text-emerald-400",
  },
  session_expired: {
    border: "border-amber-500/20",
    bg: "bg-amber-500/10",
    text: "text-amber-300",
    icon: "text-amber-400",
  },
};

export default function AuthStatusBanner({ banner }: { banner: AuthBanner }) {
  const style = STYLES[banner.kind];
  const isAlert =
    banner.kind === "error" ||
    banner.kind === "backend_offline" ||
    banner.kind === "network_offline" ||
    banner.kind === "session_expired";

  return (
    <motion.div
      key={banner.kind}
      initial={{ opacity: 0, y: -8, height: 0 }}
      animate={{ opacity: 1, y: 0, height: "auto" }}
      exit={{ opacity: 0, y: -8, height: 0 }}
      transition={{ duration: 0.2 }}
      role={isAlert ? "alert" : "status"}
      aria-live={isAlert ? "assertive" : "polite"}
      className={`mb-4 flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 ${style.border} ${style.bg}`}
    >
      {banner.kind === "checking" ? (
        <Loader2 className={`mt-0.5 h-3.5 w-3.5 animate-spin ${style.icon}`} />
      ) : banner.kind === "success" ? (
        <CheckCircle2 className={`mt-0.5 h-3.5 w-3.5 flex-shrink-0 ${style.icon}`} />
      ) : (
        <AlertCircle className={`mt-0.5 h-3.5 w-3.5 flex-shrink-0 ${style.icon}`} />
      )}
      <span className={`text-xs leading-5 ${style.text}`}>{banner.message}</span>
    </motion.div>
  );
}
