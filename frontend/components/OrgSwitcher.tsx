"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Building2, Plus, ChevronDown, Check, FolderKanban, Layers } from "lucide-react";
import { useTenant, type Organization, type Workspace, type Project } from "@/lib/tenant";
import { cn } from "@/lib/utils";

export function OrgSwitcher() {
  const {
    organizations, currentOrg, currentWorkspace, currentProject,
    workspaces, projects,
    setCurrentOrg, setCurrentWorkspace, setCurrentProject,
  } = useTenant();

  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createName, setCreateName] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  async function handleCreateOrg() {
    if (!createName.trim()) return;
    try {
      const { createOrganization } = await import("@/lib/api");
      const slug = createName.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
      const org = await createOrganization(createName.trim(), slug);
      await setCurrentOrg(org);
      setCreating(false);
      setCreateName("");
      setOpen(false);
    } catch (e) {
      console.error("Failed to create org", e);
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
          "hover:bg-white/[0.06] text-gray-300 hover:text-white"
        )}
      >
        <Building2 className="h-4 w-4 text-violet-400" />
        <span className="flex-1 truncate text-left">
          {currentOrg?.name || "Select Organization"}
        </span>
        <ChevronDown className={cn("h-3.5 w-3.5 text-gray-500 transition-transform", open && "rotate-180")} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.96 }}
            className="absolute left-0 right-0 top-full z-50 mt-1 min-w-[220px] rounded-xl border border-white/[0.08] bg-[#0c0e15] p-1.5 shadow-2xl"
          >
            <div className="mb-1 px-2 py-1 text-[10px] font-medium uppercase tracking-wider text-gray-500">
              Organizations
            </div>
            {organizations.map((org) => (
              <button
                key={org.id}
                onClick={() => { setCurrentOrg(org); setOpen(false); }}
                className={cn(
                  "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs transition-colors",
                  currentOrg?.id === org.id
                    ? "bg-violet-500/10 text-violet-300"
                    : "text-gray-400 hover:bg-white/[0.04] hover:text-white"
                )}
              >
                <Check className={cn("h-3 w-3", currentOrg?.id === org.id ? "opacity-100" : "opacity-0")} />
                <span className="flex-1 truncate text-left">{org.name}</span>
                <span className="text-[10px] text-gray-600">{org.member_count}</span>
              </button>
            ))}

            {creating ? (
              <div className="mt-1 space-y-1.5 px-1">
                <input
                  autoFocus
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreateOrg()}
                  placeholder="Organization name"
                  className="w-full rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-1.5 text-xs text-white outline-none placeholder-gray-500 focus:border-violet-500/50"
                />
                <div className="flex gap-1">
                  <button
                    onClick={handleCreateOrg}
                    className="flex-1 rounded-md bg-violet-600 py-1 text-[10px] font-medium text-white hover:bg-violet-500"
                  >
                    Create
                  </button>
                  <button
                    onClick={() => setCreating(false)}
                    className="rounded-md bg-white/[0.06] px-2 py-1 text-[10px] text-gray-400 hover:text-white"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setCreating(true)}
                className="mt-1 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-gray-500 hover:text-white"
              >
                <Plus className="h-3 w-3" />
                Create Organization
              </button>
            )}

            {currentOrg && workspaces.length > 0 && (
              <>
                <div className="mb-1 mt-2 px-2 py-1 text-[10px] font-medium uppercase tracking-wider text-gray-500">
                  Workspaces
                </div>
                {workspaces.map((ws) => (
                  <button
                    key={ws.id}
                    onClick={() => { setCurrentWorkspace(ws); setOpen(false); }}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs transition-colors",
                      currentWorkspace?.id === ws.id
                        ? "bg-cyan-500/10 text-cyan-300"
                        : "text-gray-400 hover:bg-white/[0.04] hover:text-white"
                    )}
                  >
                    <FolderKanban className="h-3 w-3 flex-shrink-0" />
                    <span className="truncate">{ws.name}</span>
                  </button>
                ))}

                {currentWorkspace && projects.length > 0 && (
                  <>
                    <div className="mb-1 mt-2 px-2 py-1 text-[10px] font-medium uppercase tracking-wider text-gray-500">
                      Projects
                    </div>
                    {projects.map((proj) => (
                      <button
                        key={proj.id}
                        onClick={() => { setCurrentProject(proj); setOpen(false); }}
                        className={cn(
                          "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs transition-colors",
                          currentProject?.id === proj.id
                            ? "bg-emerald-500/10 text-emerald-300"
                            : "text-gray-400 hover:bg-white/[0.04] hover:text-white"
                        )}
                      >
                        <Layers className="h-3 w-3 flex-shrink-0" />
                        <span className="truncate">{proj.name}</span>
                      </button>
                    ))}
                  </>
                )}
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
