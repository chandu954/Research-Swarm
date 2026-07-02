"use client";

import Link from "next/link";
import {
  Clock3,
  FileText,
  FolderOpen,
  History,
  Plus,
  Settings,
  Sparkles,
  Star,
  Trash2,
  UserRound,
  Settings2,
} from "lucide-react";
import type { UploadedDocument } from "@/lib/types";
import ThemeToggle from "./ThemeToggle";

interface SidebarProps {
  documents: UploadedDocument[];
  onClearAll: () => void;
  onNewChat: () => void;
  onOpenSettings?: () => void;
}

const fallbackConversations = [
  "AI agent frameworks",
  "LangGraph architecture",
  "RAG evaluation methods",
];

export default function Sidebar({
  documents,
  onClearAll,
  onNewChat,
  onOpenSettings,
}: SidebarProps) {
  const conversations = fallbackConversations;

  return (
    <div className="flex h-full flex-col p-3">
      <div className="flex items-center justify-between px-2 py-2">
        <Link href="/" className="flex min-w-0 items-center gap-2.5">
          <span className="brand-mark h-8 w-8">
            <Sparkles className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight text-[var(--text-primary)]">
              ResearchSwarm
            </p>
            <p className="text-[9px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]">
              Multi-agent AI
            </p>
          </div>
        </Link>
        <ThemeToggle />
      </div>

      <button
        type="button"
        onClick={onNewChat}
        className="new-research-button mt-5"
      >
        <Plus className="h-4 w-4" />
        New research
        <span className="ml-auto rounded border border-white/10 px-1.5 py-0.5 font-mono text-[9px] text-white/40">
          N
        </span>
      </button>

      <nav className="mt-5 space-y-1" aria-label="Workspace navigation">
        <button type="button" className="sidebar-nav-item">
          <FolderOpen className="h-4 w-4" />
          Documents
          <span className="sidebar-count">{documents.length}</span>
        </button>
        <button
          type="button"
          onClick={() =>
            document
              .getElementById("recent-conversations")
              ?.scrollIntoView({ behavior: "smooth" })
          }
          className="sidebar-nav-item"
        >
          <History className="h-4 w-4" />
          Research history
        </button>
        <button type="button" className="sidebar-nav-item">
          <Star className="h-4 w-4" />
          Favorites
          <span className="ml-auto text-[9px] text-[var(--text-muted)]">
            Soon
          </span>
        </button>
      </nav>

      <div
        id="recent-conversations"
        className="mt-7 min-h-0 flex-1 overflow-y-auto px-1"
      >
        <div className="mb-2 flex items-center justify-between px-2">
          <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
            Recent conversations
          </p>
          <Clock3 className="h-3 w-3 text-[var(--text-muted)]" />
        </div>

        <div className="space-y-0.5">
          {conversations.map((conversation, index) => (
            <button
              type="button"
              key={`${conversation}-${index}`}
              className="conversation-item group"
              title={conversation}
            >
              <span
                className={`conversation-dot ${
                  index === 0 ? "bg-violet-400" : "bg-white/15"
                }`}
              />
              <span className="truncate">{conversation}</span>
            </button>
          ))}
        </div>

        {documents.length > 0 && (
          <>
            <div className="mb-2 mt-7 px-2">
              <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
                Recent documents
              </p>
            </div>
            <div className="space-y-0.5">
              {documents.slice(0, 4).map((document) => (
                <button
                  type="button"
                  key={document.document_id}
                  className="conversation-item"
                >
                  <FileText className="h-3.5 w-3.5 flex-shrink-0 text-emerald-400" />
                  <span className="truncate">{document.filename}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="border-t border-[var(--border)] pt-3">
        <button
          type="button"
          onClick={onOpenSettings}
          className="sidebar-nav-item"
        >
          <Settings2 className="h-4 w-4" />
          Settings
        </button>
        <button
          type="button"
          onClick={onClearAll}
          className="sidebar-nav-item hover:!text-rose-300"
        >
          <Trash2 className="h-4 w-4" />
          Clear workspace
        </button>

        <button type="button" className="profile-card mt-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 text-[10px] font-semibold text-white">
            AS
          </span>
          <span className="min-w-0 flex-1 text-left">
            <span className="block truncate text-xs font-medium text-[var(--text-primary)]">
              AI Researcher
            </span>
            <span className="block text-[9px] text-[var(--text-muted)]">
              Local workspace
            </span>
          </span>
          <UserRound className="h-3.5 w-3.5 text-[var(--text-muted)]" />
        </button>
      </div>
    </div>
  );
}
