"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquarePlus,
  FolderOpen,
  Upload,
  FileDown,
  Settings,
  Search,
  Command,
  ArrowUp,
  ArrowDown,
  CornerDownLeft,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useFocusTrap } from "@/lib/useFocusTrap";

interface Action {
  id: string;
  label: string;
  description: string;
  icon: typeof Search;
  shortcut?: string;
  action: () => void;
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onFocusComposer: () => void;
  onOpenDocuments: () => void;
  onExportReport?: () => void;
  onOpenSettings?: () => void;
}

export default function CommandPalette({
  open,
  onClose,
  onNewChat,
  onFocusComposer,
  onOpenDocuments,
  onExportReport,
  onOpenSettings,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const paletteRef = useFocusTrap(open);

  const actions: Action[] = [
    { id: "new", label: "New Research", description: "Start a fresh research session", icon: MessageSquarePlus, shortcut: "⌘N", action: () => { onNewChat(); onClose(); } },
    { id: "focus", label: "Focus Composer", description: "Jump to the message input", icon: Search, shortcut: "⌘K", action: () => { onFocusComposer(); onClose(); } },
    { id: "documents", label: "Upload Documents", description: "Add PDFs to the workspace", icon: Upload, shortcut: "⌘U", action: () => { onOpenDocuments(); onClose(); } },
    { id: "export", label: "Export Report", description: "Download report as Markdown or HTML", icon: FileDown, shortcut: "⌘E", action: () => { onExportReport?.(); onClose(); } },
    { id: "settings", label: "Settings", description: "Configure LLM provider and models", icon: Settings, shortcut: "⌘,", action: () => { onOpenSettings?.(); onClose(); } },
  ];

  const filtered = query.trim()
    ? actions.filter((a) =>
        a.label.toLowerCase().includes(query.toLowerCase()) ||
        a.description.toLowerCase().includes(query.toLowerCase()),
      )
    : actions;

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        filtered[selectedIndex].action();
      } else if (e.key === "Escape") {
        onClose();
      }
    },
    [filtered, selectedIndex, onClose],
  );

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            ref={paletteRef}
            initial={{ opacity: 0, scale: 0.96, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -8 }}
            transition={{ duration: 0.15 }}
            className="fixed left-1/2 top-[15%] z-50 w-full max-w-lg -translate-x-1/2"
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
          >
            <div className="overflow-hidden rounded-xl border border-white/[0.08] bg-[#0a0a0f]/95 shadow-2xl backdrop-blur-xl">
              {/* Search Input */}
              <div className="flex items-center gap-2 border-b border-white/[0.06] px-3 py-2.5">
                <Search className="h-4 w-4 flex-shrink-0 text-gray-500" />
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0); }}
                  onKeyDown={handleKeyDown}
                  placeholder="Search actions..."
                  className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-gray-500"
                  autoFocus
                />
                <kbd className="flex items-center gap-0.5 rounded border border-white/[0.06] bg-white/[0.04] px-1.5 py-0.5 text-[9px] text-gray-500">
                  <Command className="h-2.5 w-2.5" />K
                </kbd>
              </div>

              {/* Action List */}
              <div className="max-h-72 overflow-y-auto p-1.5">
                {filtered.length === 0 ? (
                  <p className="px-2 py-6 text-center text-xs text-gray-500">
                    No results for &ldquo;{query}&rdquo;
                  </p>
                ) : (
                  filtered.map((action, i) => (
                    <button
                      key={action.id}
                      type="button"
                      onClick={action.action}
                      onMouseEnter={() => setSelectedIndex(i)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors",
                        i === selectedIndex
                          ? "bg-violet-500/10 text-violet-300"
                          : "text-gray-400 hover:bg-white/[0.04] hover:text-gray-200",
                      )}
                    >
                      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-white/[0.04]">
                        <action.icon className="h-3.5 w-3.5" />
                      </span>
                      <span className="flex-1">
                        <span className="block text-xs font-medium">{action.label}</span>
                        <span className="block text-[9px] text-gray-500">{action.description}</span>
                      </span>
                      <span className="flex items-center gap-1 text-[9px] text-gray-600">
                        {action.shortcut && <kbd className="rounded border border-white/[0.06] bg-white/[0.04] px-1 py-0.5">{action.shortcut}</kbd>}
                      </span>
                    </button>
                  ))
                )}
              </div>

              {/* Footer */}
              <div className="flex items-center gap-3 border-t border-white/[0.06] px-3 py-1.5">
                <span className="flex items-center gap-1 text-[9px] text-gray-600">
                  <ArrowUp className="h-2.5 w-2.5" />
                  <ArrowDown className="h-2.5 w-2.5" />
                  Navigate
                </span>
                <span className="flex items-center gap-1 text-[9px] text-gray-600">
                  <CornerDownLeft className="h-2.5 w-2.5" />
                  Select
                </span>
                <span className="flex items-center gap-1 text-[9px] text-gray-600">
                  Esc Close
                </span>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
