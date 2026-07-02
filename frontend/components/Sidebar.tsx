"use client";

import { useEffect, useState } from "react";
import {
  Clock3,
  FileText,
  FolderOpen,
  History,
  Plus,
  Search,
  Settings2,
  Sparkles,
  Star,
  Trash2,
  Bookmark,
  LayoutTemplate,
  Layers,
  MessageSquare,
} from "lucide-react";
import type { UploadedDocument } from "@/lib/types";
import { listConversations } from "@/lib/api";
import ThemeToggle from "./ThemeToggle";
import Link from "next/link";

interface SidebarProps {
  documents: UploadedDocument[];
  recentQueries?: string[];
  collections?: string[];
  onClearAll: () => void;
  onNewChat: () => void;
  onOpenDocuments?: () => void;
  onOpenSettings?: () => void;
}

interface Conversation {
  id: string;
  query?: string;
  timestamp?: string;
  turn_count?: number;
}

const navItems = [
  { icon: History, label: "Recent", active: true },
  { icon: Bookmark, label: "Collections", active: false },
  { icon: LayoutTemplate, label: "Templates", active: false },
  { icon: Star, label: "Pinned", active: false },
];

export default function Sidebar({
  documents,
  recentQueries = [],
  collections = [],
  onClearAll,
  onNewChat,
  onOpenDocuments,
  onOpenSettings,
}: SidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    setLoading(true);
    listConversations()
      .then((data) => {
        const convs = (data.conversations || []).map((c: any) => ({
          id: c.id || c.conversation_id || "",
          query: c.query || c.metadata?.query || "",
          timestamp: c.timestamp || c.created_at || "",
          turn_count: c.turn_count || 0,
        }));
        setConversations(convs);
      })
      .catch(() => {
        /* fall back to local queries */
      })
      .finally(() => setLoading(false));
  }, []);

  const displayConversations =
    conversations.length > 0
      ? conversations
      : recentQueries.map((q, i) => ({
          id: `local-${i}`,
          query: q,
          timestamp: "",
          turn_count: 0,
        }));

  const filtered = searchQuery
    ? displayConversations.filter((c) =>
        (c.query || "").toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : displayConversations;

  return (
    <div className="flex h-full flex-col p-3">
      <div className="flex items-center justify-between px-2 py-2">
        <Link href="/" className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600">
            <Sparkles className="h-4 w-4 text-white" />
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

      <nav className="mt-5 space-y-0.5" aria-label="Workspace navigation">
        {navItems.map(({ icon: Icon, label, active }) => (
          <button
            key={label}
            type="button"
            className={`sidebar-nav-item ${active ? "active" : ""}`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
        <button
          type="button"
          onClick={onOpenDocuments}
          className="sidebar-nav-item"
        >
          <FolderOpen className="h-4 w-4" />
          Documents
          <span className="sidebar-count">{documents.length}</span>
        </button>
      </nav>

      {collections.length > 0 && (
        <div className="mt-6 px-2">
          <div className="mb-2 flex items-center gap-2">
            <Layers className="h-3 w-3 text-[var(--text-muted)]" />
            <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
              Collections
            </p>
          </div>
          <div className="space-y-0.5">
            {collections.map((collection) => (
              <button
                key={collection}
                type="button"
                className="conversation-item group"
              >
                <span className="conversation-dot bg-violet-400/40" />
                <span className="truncate">{collection}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-6 min-h-0 flex-1 overflow-y-auto px-1">
        <div className="mb-2 flex items-center justify-between px-2">
          <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
            Memory browser
          </p>
          <MessageSquare className="h-3 w-3 text-[var(--text-muted)]" />
        </div>

        <div className="relative mb-2 px-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3 w-3 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] py-1.5 pl-7 pr-2 text-[10px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none focus:border-violet-400/30"
          />
        </div>

        <div className="space-y-0.5">
          {loading ? (
            <p className="px-2 py-3 text-[10px] text-[var(--text-muted)]">
              Loading conversations...
            </p>
          ) : filtered.length === 0 ? (
            <p className="px-2 py-3 text-[10px] text-[var(--text-muted)]">
              {searchQuery
                ? "No matching conversations"
                : "No conversations yet. Start a new research."}
            </p>
          ) : (
            filtered.map((conv) => (
              <button
                type="button"
                key={conv.id}
                className="conversation-item group w-full text-left"
                title={conv.query}
              >
                <span className="conversation-dot bg-white/15" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[11px] text-[var(--text-secondary)]">
                    {conv.query || "Untitled"}
                  </span>
                  {conv.timestamp && (
                    <span className="block text-[8px] text-[var(--text-muted)]">
                      {new Date(conv.timestamp).toLocaleDateString()}
                      {conv.turn_count ? ` · ${conv.turn_count} turns` : ""}
                    </span>
                  )}
                </span>
              </button>
            ))
          )}
        </div>

        {documents.length > 0 && (
          <div className="mt-6">
            <div className="mb-2 px-2">
              <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
                Recent documents
              </p>
            </div>
            <div className="space-y-0.5">
              {documents.slice(0, 5).map((document) => (
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
          </div>
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
        </button>
      </div>
    </div>
  );
}
