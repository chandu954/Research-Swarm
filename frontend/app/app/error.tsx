"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, Home, RefreshCw } from "lucide-react";

export default function WorkspaceError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[WorkspaceError]", error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--bg)] p-8">
      <div className="flex max-w-md flex-col items-center gap-6 text-center">
        <span className="flex h-16 w-16 items-center justify-center rounded-3xl bg-rose-500/10 text-rose-400">
          <AlertTriangle className="h-8 w-8" />
        </span>
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">
            Research workspace crashed
          </h1>
          <p className="mt-2 text-sm text-[var(--text-muted)]">
            {error.message || "The research workspace encountered an unexpected error."}
          </p>
          {error.digest && (
            <p className="mt-1 text-[10px] text-[var(--text-muted)]">
              Error ID: {error.digest}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={reset}
            className="inline-flex items-center gap-2 rounded-xl border border-white/[0.08] bg-[var(--surface)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-white/[0.06]"
          >
            <RefreshCw className="h-4 w-4" />
            Try again
          </button>
          <Link
            href="/app"
            className="inline-flex items-center gap-2 rounded-xl bg-violet-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-600"
          >
            <Home className="h-4 w-4" />
            New session
          </Link>
        </div>
      </div>
    </div>
  );
}
