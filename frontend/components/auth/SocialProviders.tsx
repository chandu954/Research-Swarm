"use client";

import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

export const SOCIAL_PROVIDERS = [
  {
    id: "google" as const,
    label: "Google",
    icon: () => (
      <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
        <path
          fill="currentColor"
          d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        />
        <path
          fill="currentColor"
          d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        />
        <path
          fill="currentColor"
          d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        />
        <path
          fill="currentColor"
          d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        />
      </svg>
    ),
  },
];

interface SocialProvidersProps {
  disabled: boolean;
  isLoading: (provider: "google") => boolean;
  onSelect: (provider: "google") => void;
}

export default function SocialProviders({
  disabled,
  isLoading,
  onSelect,
}: SocialProvidersProps) {
  return (
    <div className="mb-5 space-y-2.5">
      {SOCIAL_PROVIDERS.map((provider, index) => (
        <motion.button
          key={provider.id}
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 + index * 0.05, duration: 0.3 }}
          onClick={() => onSelect(provider.id)}
          disabled={disabled}
          aria-label={`Continue with ${provider.label}`}
          aria-busy={isLoading(provider.id)}
          className="group relative flex w-full items-center justify-center gap-3 overflow-hidden rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm font-medium text-gray-300 transition-all hover:border-white/[0.14] hover:bg-white/[0.06] hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isLoading(provider.id) && (
            <span className="absolute inset-0 flex items-center justify-center bg-white/[0.04] backdrop-blur-sm">
              <Loader2 className="h-4 w-4 animate-spin text-gray-300" />
            </span>
          )}
          <provider.icon />
          <span>Continue with {provider.label}</span>
        </motion.button>
      ))}
    </div>
  );
}
