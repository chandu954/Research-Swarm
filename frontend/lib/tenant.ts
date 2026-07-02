"use client";

import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { useAuth } from "./auth";

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

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TenantContext = createContext<TenantContextType | null>(null);

function getHeaders(token: string | null) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

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
      const res = await fetch(`${API_URL}/organizations`, {
        headers: getHeaders(token),
      });
      if (res.ok) {
        const orgs: Organization[] = await res.json();
        setOrganizations(orgs);
        if (!currentOrg && orgs.length > 0) {
          const storedId = localStorage.getItem("research-swarm-org-id");
          const found = storedId ? orgs.find(o => o.id === storedId) : orgs[0];
          setCurrentOrgState(found || orgs[0]);
        }
      }
    } catch { /* offline */ }
    setIsLoading(false);
  }, [token, currentOrg]);

  const refreshWorkspaces = useCallback(async () => {
    if (!token || !currentOrg) return;
    try {
      const res = await fetch(`${API_URL}/organizations/${currentOrg.id}/workspaces`, {
        headers: getHeaders(token),
      });
      if (res.ok) {
        const wsList: Workspace[] = await res.json();
        setWorkspaces(wsList);
        if (!currentWorkspace && wsList.length > 0) {
          const storedId = localStorage.getItem("research-swarm-ws-id");
          const found = storedId ? wsList.find(w => w.id === storedId) : wsList[0];
          setCurrentWorkspaceState(found || wsList[0]);
        }
      }
    } catch { /* offline */ }
  }, [token, currentOrg, currentWorkspace]);

  const refreshProjects = useCallback(async () => {
    if (!token || !currentOrg || !currentWorkspace) return;
    try {
      const res = await fetch(
        `${API_URL}/organizations/${currentOrg.id}/workspaces/${currentWorkspace.id}/projects`,
        { headers: getHeaders(token) }
      );
      if (res.ok) {
        const projList: Project[] = await res.json();
        setProjects(projList);
        if (projList.length === 0) setCurrentProjectState(null);
      }
    } catch { /* offline */ }
  }, [token, currentOrg, currentWorkspace]);

  useEffect(() => { refreshOrganizations(); }, [refreshOrganizations]);
  useEffect(() => { refreshWorkspaces(); }, [refreshWorkspaces]);
  useEffect(() => { refreshProjects(); }, [refreshProjects]);

  const setCurrentOrg = useCallback(async (org: Organization) => {
    setCurrentOrgState(org);
    setCurrentWorkspaceState(null);
    setCurrentProjectState(null);
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
