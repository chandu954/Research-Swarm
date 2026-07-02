"use client";

import { Component, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: unknown) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: unknown) {
    console.error("[ErrorBoundary]", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex min-h-[200px] items-center justify-center rounded-2xl border border-rose-400/20 bg-rose-500/[0.04] p-8">
          <div className="flex max-w-md flex-col items-center gap-4 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-400">
              <AlertTriangle className="h-6 w-6" />
            </span>
            <div>
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                Something went wrong
              </h3>
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                {this.state.error?.message || "An unexpected error occurred."}
              </p>
            </div>
            <button
              type="button"
              onClick={() => this.setState({ hasError: false, error: null })}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.06] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-white/[0.06]"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
