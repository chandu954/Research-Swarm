"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Search, Sparkles, Menu, Settings2,
  ChevronDown, LogOut,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import ThemeToggle from "./ThemeToggle";
import { OrgSwitcher } from "./OrgSwitcher";
import { useAuth } from "@/lib/auth";

interface TopbarProps {
  onToggleSidebar: () => void;
  onOpenSettings: () => void;
  onOpenPalette: () => void;
}

export default function Topbar({
  onToggleSidebar,
  onOpenSettings,
  onOpenPalette,
}: TopbarProps) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [profileOpen, setProfileOpen] = useState(false);

  const initials = user?.name
    ? user.name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)
    : "U";

  return (
    <header className="relative z-40 flex h-12 items-center justify-between border-b border-[var(--border)] bg-[var(--surface)]/80 px-3 backdrop-blur-xl">
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleSidebar}
          className="icon-button h-8 w-8 lg:hidden"
          aria-label="Toggle sidebar"
        >
          <Menu className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600">
            <Sparkles className="h-3.5 w-3.5 text-white" />
          </span>
          <span className="hidden text-sm font-semibold text-[var(--text-primary)] sm:block">
            ResearchSwarm
          </span>
        </div>

        <div className="ml-2 hidden md:block w-48">
          <OrgSwitcher />
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <button
          onClick={onOpenPalette}
          className="flex h-9 w-56 items-center gap-2 rounded-lg border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface-hover)_35%,transparent)] px-3 text-[11px] text-[var(--text-muted)] transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text-secondary)]"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Search</span>
          <kbd className="ml-auto hidden rounded border border-[var(--border)] bg-[var(--surface)] px-1 font-mono text-[9px] sm:inline">
            ⌘K
          </kbd>
        </button>

        <ThemeToggle />

        <div className="relative">
          <button
            onClick={() => setProfileOpen((o) => !o)}
            className="flex h-9 items-center gap-2 rounded-lg border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface-hover)_25%,transparent)] pl-2 pr-2.5 text-[11px] text-[var(--text-secondary)] transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--surface-hover)]"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 text-[9px] font-semibold text-white">
              {initials}
            </span>
            <span className="hidden max-w-[90px] truncate lg:inline">
              {user?.name?.split(" ")[0] || "Profile"}
            </span>
            <ChevronDown className="h-3 w-3 text-[var(--text-muted)]" />
          </button>
          <AnimatePresence>
            {profileOpen && (
              <motion.div
                initial={{ opacity: 0, y: -4, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.97 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 top-full z-50 mt-2 w-56 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl"
              >
                <div className="flex items-center gap-3 border-b border-[var(--border)] px-3.5 py-3">
                  <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 text-xs font-bold text-white">
                    {initials}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-semibold text-[var(--text-primary)]">
                      {user?.name || "Guest"}
                    </p>
                    <p className="truncate text-[10px] text-[var(--text-muted)]">
                      {user?.email}
                    </p>
                  </div>
                </div>
                <div className="p-1.5">
                  <button
                    onClick={() => {
                      setProfileOpen(false);
                      onOpenSettings();
                    }}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
                  >
                    <Settings2 className="h-4 w-4 text-[var(--text-muted)]" />
                    Settings
                  </button>
                </div>
                <div className="border-t border-[var(--border)] p-1.5">
                  <button
                    onClick={() => {
                      setProfileOpen(false);
                      logout();
                      router.push("/login");
                    }}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs text-rose-400 transition-colors hover:bg-[color-mix(in_srgb,#f43f5e_8%,transparent)]"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign out
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
}
