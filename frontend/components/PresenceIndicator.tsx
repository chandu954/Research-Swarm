"use client";

import { useEffect, useState } from "react";
import { collaborationClient } from "@/lib/websocket";
import type { PresenceUser } from "@/lib/websocket";
import { Users } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  workspaceId?: string;
  token?: string;
}

export function PresenceIndicator({ workspaceId, token }: Props) {
  const [users, setUsers] = useState<PresenceUser[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!workspaceId || !token) return;
    collaborationClient.connect(workspaceId, token, {
      onPresence: setUsers,
    });
    return () => collaborationClient.disconnect();
  }, [workspaceId, token]);

  if (!workspaceId) return null;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
      >
        <Users className="h-3 w-3" />
        <span>{users.length > 0 ? users.length : "—"}</span>
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-48 rounded-lg border border-white/5 bg-[var(--surface-elevated)] p-2 shadow-xl">
          <p className="px-1 pb-1 text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Online
          </p>
          {users.length === 0 ? (
            <p className="px-1 py-2 text-[11px] text-[var(--text-muted)]">No one else online</p>
          ) : (
            users.map((u) => (
              <div key={u.userId} className="flex items-center gap-2 rounded px-1 py-1.5 text-[11px]">
                <span className={cn("h-2 w-2 rounded-full", u.status === "online" ? "bg-green-500" : "bg-yellow-500")} />
                <span className="text-[var(--text-secondary)]">{u.name}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
