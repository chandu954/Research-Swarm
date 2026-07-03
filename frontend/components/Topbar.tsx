"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Command, Search, Sparkles, Menu, Settings2,
  UserRound, ChevronDown, LogOut, Network, Globe2,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import ThemeToggle from "./ThemeToggle";
import { OrgSwitcher } from "./OrgSwitcher";
import { useAuth } from "@/lib/auth";

interface TopbarProps {
  onToggleSidebar: () => void;
  onOpenSettings: () => void;
  onOpenPalette: () => void;
  provider: string;
}

export default function Topbar({
  onToggleSidebar,
  onOpenSettings,
  onOpenPalette,
  provider,
}: TopbarProps) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [profileOpen, setProfileOpen] = useState(false);

  const initials = user?.name
    ? user.name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)
    : "U";

  return (
    <header className="flex h-12 items-center justify-between border-b border-white/[0.06] bg-[var(--surface)]/80 px-3 backdrop-blur-xl">
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
          <span className="hidden rounded-md border border-violet-400/20 bg-violet-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-violet-300 sm:inline">
            v3
          </span>
        </div>

        <div className="ml-2 hidden md:block w-48">
          <OrgSwitcher />
        </div>

        <div className="ml-2 hidden items-center gap-1.5 md:flex">
          <span className="tech-badge">
            <Network className="h-3 w-3 text-violet-400" />
            LangGraph
          </span>
          <span className="tech-badge">
            <Globe2 className="h-3 w-3 text-cyan-400" />
            {provider === "openrouter" ? "OpenRouter" : "Ollama"}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <button
          onClick={onOpenPalette}
          className="flex h-8 items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 text-[11px] text-[var(--text-muted)] transition-colors hover:border-white/[0.12] hover:text-[var(--text-secondary)]"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Search</span>
          <kbd className="ml-1 hidden rounded border border-white/[0.06] bg-white/[0.04] px-1 font-mono text-[9px] sm:inline">
            ⌘K
          </kbd>
        </button>

        <button
          onClick={onOpenSettings}
          className="icon-button h-8 w-8"
          aria-label="Settings"
        >
          <Settings2 className="h-4 w-4" />
        </button>

        <ThemeToggle />

        <div className="relative">
          <button
            onClick={() => setProfileOpen((o) => !o)}
            className="flex h-8 items-center gap-1.5 rounded-lg pl-1.5 pr-2 text-[11px] text-[var(--text-secondary)] transition-colors hover:bg-white/[0.04]"
          >
            <span className="flex h-5 w-5 items-center justify-center rounded-md bg-gradient-to-br from-violet-500 to-indigo-600 text-[8px] font-semibold text-white">
              {initials}
            </span>
            <ChevronDown className="h-3 w-3 text-[var(--text-muted)]" />
          </button>
          <AnimatePresence>
            {profileOpen && (
              <motion.div
                initial={{ opacity: 0, y: -4, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.96 }}
                className="absolute right-0 top-full z-50 mt-1 w-48 overflow-hidden rounded-xl border border-white/[0.08] bg-[var(--surface)] py-1 shadow-2xl"
              >
                <div className="border-b border-white/[0.06] px-3 py-2">
                  <p className="text-xs font-medium text-[var(--text-primary)]">{user?.name}</p>
                  <p className="text-[10px] text-[var(--text-muted)]">{user?.email}</p>
                </div>
                <button
                  onClick={onOpenSettings}
                  className="flex w-full items-center gap-2 px-3 py-2 text-[11px] text-[var(--text-secondary)] transition-colors hover:bg-white/[0.04]"
                >
                  <Settings2 className="h-3.5 w-3.5" />
                  Settings
                </button>
                <button
                  onClick={() => { logout(); router.push("/login"); }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-[11px] text-rose-400 transition-colors hover:bg-white/[0.04]"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  Sign out
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
}
