"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Loader2 } from "lucide-react";
import type { ConfirmOptions } from "@/lib/confirm-context";
import { useFocusTrap } from "@/lib/useFocusTrap";
import { useReducedMotion } from "@/lib/useReducedMotion";

interface ConfirmDialogProps {
  open: boolean;
  options: ConfirmOptions | null;
  loading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

// Shared confirmation modal. Accessible by default: role=alertdialog,
// Escape to cancel, focus trapped inside, focus returns to the trigger
// (the trigger retains focus because it is never blurred by the overlay).
export default function ConfirmDialog({
  open,
  options,
  loading,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const panelRef = useFocusTrap(open);
  const reducedMotion = useReducedMotion();
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  const transition = reducedMotion ? { duration: 0 } : { duration: 0.15 };

  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !loading) {
        event.preventDefault();
        onCancel();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, loading, onCancel]);

  useEffect(() => {
    if (!open || loading) return;
    cancelButtonRef.current?.focus();
  }, [open, loading]);

  return (
    <AnimatePresence>
      {open && options && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={transition}
          className="confirm-overlay fixed inset-0 z-[60] flex items-center justify-center p-4"
          role="presentation"
        >
          <div
            className="absolute inset-0"
            aria-hidden
            onClick={() => !loading && onCancel()}
          />
          <motion.div
            ref={panelRef}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
            aria-describedby="confirm-dialog-description"
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={transition}
            className="confirm-panel relative z-10 w-full max-w-sm p-5"
          >
            <div className="flex items-start gap-3">
              <span
                className={
                  options.destructive
                    ? "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-rose-500/10 text-rose-400"
                    : "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-violet-500/10 text-violet-400"
                }
                aria-hidden
              >
                {options.icon ? (
                  <options.icon className="h-5 w-5" />
                ) : (
                  <AlertTriangle className="h-5 w-5" />
                )}
              </span>
              <div className="min-w-0">
                <h2
                  id="confirm-dialog-title"
                  className="text-sm font-semibold tracking-tight text-[var(--text-primary)]"
                >
                  {options.title}
                </h2>
                {options.description && (
                  <div
                    id="confirm-dialog-description"
                    className="mt-1.5 text-xs leading-relaxed text-[var(--text-secondary)]"
                  >
                    {options.description}
                  </div>
                )}
              </div>
            </div>

            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                ref={cancelButtonRef}
                type="button"
                onClick={onCancel}
                disabled={loading}
                className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text-primary)] disabled:opacity-50"
              >
                {options.cancelLabel ?? "Cancel"}
              </button>
              <button
                type="button"
                onClick={onConfirm}
                disabled={loading}
                className={
                  options.destructive
                    ? "inline-flex items-center gap-1.5 rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-rose-500 disabled:opacity-60"
                    : "inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-violet-500 disabled:opacity-60"
                }
              >
                {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {options.confirmLabel ?? "Confirm"}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
