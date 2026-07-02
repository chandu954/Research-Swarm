"use client";

import { useEffect } from "react";
import Link from "next/link";
import {
  FileText,
  Home,
  MessageSquarePlus,
  Search,
  X,
} from "lucide-react";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onFocusComposer: () => void;
  onOpenDocuments: () => void;
}

export default function CommandPalette({
  open,
  onClose,
  onNewChat,
  onFocusComposer,
  onOpenDocuments,
}: CommandPaletteProps) {
  useEffect(() => {
    if (!open) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [onClose, open]);

  if (!open) return null;

  const actions = [
    {
      label: "Focus research composer",
      detail: "Start typing a question",
      icon: Search,
      action: onFocusComposer,
      shortcut: "/",
    },
    {
      label: "New research",
      detail: "Clear the current conversation",
      icon: MessageSquarePlus,
      action: () => {
        onNewChat();
        onClose();
      },
      shortcut: "N",
    },
    {
      label: "Add documents",
      detail: "Upload PDF evidence",
      icon: FileText,
      action: () => {
        onOpenDocuments();
        onClose();
      },
      shortcut: "D",
    },
  ] as const;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/65 px-4 pt-[14vh] backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="command-title"
        className="command-palette"
      >
        <div className="flex items-center gap-3 border-b border-white/[0.06] px-4 py-3">
          <Search className="h-4 w-4 text-violet-400" />
          <div className="min-w-0 flex-1">
            <h2 id="command-title" className="text-sm text-[var(--text-primary)]">
              Quick actions
            </h2>
            <p className="text-[10px] text-[var(--text-muted)]">
              Jump anywhere in the workspace
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="icon-button h-7 w-7"
            aria-label="Close command palette"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="p-2">
          {actions.map(({ label, detail, icon: Icon, action, shortcut }) => (
            <button
              type="button"
              key={label}
              onClick={action}
              className="command-item"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.03] text-[var(--text-secondary)]">
                <Icon className="h-3.5 w-3.5" />
              </span>
              <span className="min-w-0 flex-1 text-left">
                <span className="block text-xs text-[var(--text-primary)]">
                  {label}
                </span>
                <span className="block text-[10px] text-[var(--text-muted)]">
                  {detail}
                </span>
              </span>
              <kbd>{shortcut}</kbd>
            </button>
          ))}

          <Link href="/" onClick={onClose} className="command-item">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.03] text-[var(--text-secondary)]">
              <Home className="h-3.5 w-3.5" />
            </span>
            <span className="min-w-0 flex-1 text-left">
              <span className="block text-xs text-[var(--text-primary)]">
                Return to landing page
              </span>
              <span className="block text-[10px] text-[var(--text-muted)]">
                View the ResearchSwarm overview
              </span>
            </span>
          </Link>
        </div>
      </section>
    </div>
  );
}
