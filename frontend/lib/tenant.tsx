"use client";

import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { useAuth } from "./auth";
import { api } from "./api-client";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  avatar_url?: string | null;
  owner_id: string;
  member_count: number;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  organization_id: string;
  owner_id: string;
  member_count: number;
  is_active: boolean;
}

export interface Project {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  organization_id: string;
  workspace_id: string;
  owner_id: string;
  is_active: boolean;
}

interface TenantContextType {
  organizations: Organization[];
  currentOrg: Organization | null;
  currentWorkspace: Workspace | null;
  currentProject: Project | null;
  workspaces: Workspace[];
  projects: Project[];
  setCurrentOrg: (org: Organization) => Promise<void>;
  setCurrentWorkspace: (ws: Workspace) => Promise<void>;
  setCurrentProject: (proj: Project | null) => void;
  refreshOrganizations: () => Promise<void>;
  refreshWorkspaces: () => Promise<void>;
  refreshProjects: () => Promise<void>;
  isLoading: boolean;
}

const TenantContext = createContext<TenantContextType | null>(null);

export function TenantProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [currentOrg, setCurrentOrgState] = useState<Organization | null>(null);
  const [currentWorkspace, setCurrentWorkspaceState] = useState<Workspace | null>(null);
  const [currentProject, setCurrentProjectState] = useState<Project | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const refreshOrganizations = useCallback(async () => {
    if (!token) return;
    try {
      const orgs: Organization[] = await api.get("/organizations");
      setOrganizations(orgs);
      // Only auto-select an org if none is selected yet
      setCurrentOrgState(prev => {
        if (prev) return prev;
        const storedId = localStorage.getItem("research-swarm-org-id");
        const found = storedId ? orgs.find(o => o.id === storedId) : orgs[0];
        return found || orgs[0] || null;
      });
    } catch (err) { console.warn("Failed to load organizations:", err); }
    setIsLoading(false);
  // Intentionally exclude currentOrg — including it would cause an
  // infinite loop (org change triggers refresh which changes org state).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const refreshWorkspaces = useCallback(async () => {
    if (!token || !currentOrg) return;
    try {
      const wsList: Workspace[] = await api.get(`/organizations/${currentOrg.id}/workspaces`);
      setWorkspaces(wsList);
      // Auto-select workspace only if none selected, or if selected one not in new list
      setCurrentWorkspaceState(prev => {
        if (prev && wsList.find(w => w.id === prev.id)) return prev;
        const storedId = localStorage.getItem("research-swarm-ws-id");
        const found = storedId ? wsList.find(w => w.id === storedId) : wsList[0];
        return found || wsList[0] || null;
      });
    } catch (err) { console.warn("Failed to load workspaces:", err); }
  // Exclude currentWorkspace to avoid loop — workspace selection
  // should not trigger a full workspace list refresh.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, currentOrg]);

  const refreshProjects = useCallback(async () => {
    if (!token || !currentOrg || !currentWorkspace) return;
    try {
      const projList: Project[] = await api.get(`/organizations/${currentOrg.id}/workspaces/${currentWorkspace.id}/projects`);
      setProjects(projList);
      if (projList.length === 0) setCurrentProjectState(null);
    } catch (err) { console.warn("Failed to load projects:", err); }
  }, [token, currentOrg, currentWorkspace]);

  useEffect(() => { refreshOrganizations(); }, [refreshOrganizations]);
  useEffect(() => { refreshWorkspaces(); }, [refreshWorkspaces]);
  useEffect(() => { refreshProjects(); }, [refreshProjects]);

  const setCurrentOrg = useCallback(async (org: Organization) => {
    setCurrentOrgState(org);
    setCurrentWorkspaceState(null);
    setCurrentProjectState(null);
    setWorkspaces([]);
    setProjects([]);
    localStorage.setItem("research-swarm-org-id", org.id);
    localStorage.removeItem("research-swarm-ws-id");
  }, []);

  const setCurrentWorkspace = useCallback(async (ws: Workspace) => {
    setCurrentWorkspaceState(ws);
    setCurrentProjectState(null);
    localStorage.setItem("research-swarm-ws-id", ws.id);
  }, []);

  const setCurrentProject = useCallback((proj: Project | null) => {
    setCurrentProjectState(proj);
  }, []);

  return (
    <TenantContext.Provider value={{
      organizations, currentOrg, currentWorkspace, currentProject,
      workspaces, projects,
      setCurrentOrg, setCurrentWorkspace, setCurrentProject,
      refreshOrganizations, refreshWorkspaces, refreshProjects,
      isLoading,
    }}>
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant() {
  const ctx = useContext(TenantContext);
  if (!ctx) throw new Error("useTenant must be used within TenantProvider");
  return ctx;
}
