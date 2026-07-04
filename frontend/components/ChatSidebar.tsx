"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, MessageSquare, X } from "lucide-react";
import { collaborationClient } from "@/lib/websocket";
import { useAuth } from "@/lib/auth";
import type { ChatMessage, TypingUser } from "@/lib/websocket";

interface Props {
  open: boolean;
  onClose: () => void;
}

const DEFAULT_WORKSPACE_ID = "default";

export function ChatSidebar({ open, onClose }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [typingUsers, setTypingUsers] = useState<TypingUser[]>([]);
  const listRef = useRef<HTMLDivElement>(null);
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { user, token } = useAuth();

  useEffect(() => {
    if (!open || !token) return;
    const cbs = {
      onChatMessage: (msg: ChatMessage) => {
        setMessages((prev) => [...prev, msg]);
      },
      onChatHistory: (history: ChatMessage[]) => {
        setMessages(history);
      },
      onTyping: (users: TypingUser[]) => {
        setTypingUsers(users);
      },
    };
    if (open && token) {
      collaborationClient.connect(DEFAULT_WORKSPACE_ID, token, cbs);
    }
    return () => {
      collaborationClient.disconnect();
    };
  }, [open, token]);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text) return;
    collaborationClient.sendChat(text);
    setInput("");
  }, [input]);

  const handleInputChange = useCallback((value: string) => {
    setInput(value);
    collaborationClient.sendTyping(true);
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    typingTimeoutRef.current = setTimeout(() => {
      collaborationClient.sendTyping(false);
    }, 3000);
  }, []);

  const typingText = typingUsers.length > 0
    ? typingUsers.length === 1
      ? `${typingUsers[0].name} is typing...`
      : `${typingUsers.length} people are typing...`
    : null;

  return (
    <aside
      className={`fixed right-0 top-0 z-40 flex h-full w-80 flex-col border-l border-white/[0.06] bg-[var(--surface)] transition-transform ${
        open ? "translate-x-0" : "translate-x-full"
      }`}
    >
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-[var(--text-muted)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">Workspace Chat</span>
        </div>
        <button onClick={onClose} className="icon-button h-7 w-7" aria-label="Close chat">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div ref={listRef} className="flex-1 space-y-2 overflow-y-auto px-4 py-3">
        {messages.length === 0 && (
          <p className="py-8 text-center text-[11px] text-[var(--text-muted)]">
            No messages yet. Say hello!
          </p>
        )}
        {messages.map((msg) => {
          const isOwn = msg.userId === user?.id;
          return (
            <div key={msg.id} className={`flex flex-col ${isOwn ? "items-end" : "items-start"}`}>
              <div
                className={`max-w-[85%] rounded-lg px-3 py-2 ${
                  isOwn
                    ? "bg-violet-600 text-white"
                    : "bg-white/[0.04] text-[var(--text-secondary)]"
                }`}
              >
                <p className="text-[10px] font-semibold text-[var(--text-muted)]">{msg.userName}</p>
                <p className="mt-0.5 text-[13px] leading-relaxed">{msg.content}</p>
              </div>
              <span className="mt-0.5 px-1 text-[9px] text-[var(--text-muted)]">
                {new Date(msg.timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
          );
        })}
        {typingText && (
          <p className="px-1 text-[10px] italic text-[var(--text-muted)]">{typingText}</p>
        )}
      </div>

      <div className="border-t border-white/[0.06] p-3">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Type a message..."
            className="flex-1 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus:border-violet-500/50"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-600 text-white transition-opacity hover:opacity-90 disabled:opacity-30"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
