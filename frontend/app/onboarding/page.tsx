"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles, Building2, Layers, FolderOpen, CheckCircle2,
  ArrowRight, ArrowLeft, Loader2, Hash,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STEPS = [
  { id: "welcome", icon: Sparkles, label: "Welcome" },
  { id: "org", icon: Building2, label: "Organization" },
  { id: "workspace", icon: Layers, label: "Workspace" },
  { id: "project", icon: FolderOpen, label: "Project" },
  { id: "complete", icon: CheckCircle2, label: "Done" },
];

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "workspace";
}

export default function OnboardingPage() {
  const { token } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [wsName, setWsName] = useState("General");
  const [wsSlug, setWsSlug] = useState("general");
  const [projectName, setProjectName] = useState("Default Project");
  const [projectSlug, setProjectSlug] = useState("default");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [createdOrgId, setCreatedOrgId] = useState<string | null>(null);
  const [createdWsId, setCreatedWsId] = useState<string | null>(null);

  const canAdvance = useCallback(() => {
    switch (step) {
      case 0: return true;
      case 1: return orgName.trim().length > 0;
      case 2: return wsName.trim().length > 0;
      case 3: return projectName.trim().length > 0;
      default: return true;
    }
  }, [step, orgName, wsName, projectName]);

  async function handleNext() {
    if (!canAdvance()) return;
    setError("");

    if (step === 1) {
      setLoading(true);
      try {
        const res = await fetch(`${API_URL}/organizations`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            name: orgName.trim(),
            slug: orgSlug || slugify(orgName),
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || "Failed to create organization");
        }
        const org = await res.json();
        setCreatedOrgId(org.id);
        localStorage.setItem("research-swarm-org-id", org.id);
      } catch (err: any) {
        setError(err.message || "Something went wrong");
        setLoading(false);
        return;
      }
      setLoading(false);
    }

    if (step === 2 && createdOrgId) {
      setLoading(true);
      try {
        const res = await fetch(`${API_URL}/organizations/${createdOrgId}/workspaces`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            name: wsName.trim(),
            slug: wsSlug || slugify(wsName),
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || "Failed to create workspace");
        }
        const ws = await res.json();
        setCreatedWsId(ws.id);
        localStorage.setItem("research-swarm-ws-id", ws.id);
      } catch (err: any) {
        setError(err.message || "Something went wrong");
        setLoading(false);
        return;
      }
      setLoading(false);
    }

    if (step === 3 && createdOrgId && createdWsId) {
      setLoading(true);
      try {
        const res = await fetch(
          `${API_URL}/organizations/${createdOrgId}/workspaces/${createdWsId}/projects`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              name: projectName.trim(),
              slug: projectSlug || slugify(projectName),
            }),
          }
        );
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || "Failed to create project");
        }
        const project = await res.json();
        localStorage.setItem("research-swarm-project-id", project.id);
      } catch (err: any) {
        setError(err.message || "Something went wrong");
        setLoading(false);
        return;
      }
      setLoading(false);
    }

    if (step === STEPS.length - 1) {
      router.push("/app");
      return;
    }

    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  }

  function handleBack() {
    setError("");
    setStep((s) => Math.max(s - 1, 0));
  }

  const isLastStep = step === STEPS.length - 1;

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0a0a0f] p-4">
      <div className="w-full max-w-lg">
        <div className="mb-10 flex items-center justify-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-cyan-500">
            <Sparkles className="h-4 w-4 text-white" />
          </span>
          <span className="text-sm font-semibold text-white">ResearchSwarm</span>
        </div>

        <div className="mb-8 flex items-center justify-center gap-2">
          {STEPS.map((s, i) => (
            <div key={s.id} className="flex items-center gap-2">
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-medium transition-colors ${
                  i <= step
                    ? "bg-violet-500 text-white"
                    : "border border-white/[0.08] text-gray-500"
                }`}
              >
                {i < step ? <CheckCircle2 className="h-3.5 w-3.5" /> : i + 1}
              </div>
              <span
                className={`hidden text-xs sm:inline ${
                  i <= step ? "text-gray-300" : "text-gray-600"
                }`}
              >
                {s.label}
              </span>
              {i < STEPS.length - 1 && (
                <div
                  className={`mx-1 h-px w-6 ${
                    i < step ? "bg-violet-500" : "bg-white/[0.06]"
                  }`}
                />
              )}
            </div>
          ))}
        </div>

        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.035] p-8 shadow-2xl shadow-black/20 backdrop-blur-xl">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
            >
              {step === 0 && (
                <div className="text-center">
                  <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-500/10 text-violet-300">
                    <Sparkles className="h-6 w-6" />
                  </span>
                  <h1 className="mt-6 text-xl font-semibold text-white">
                    Welcome to ResearchSwarm
                  </h1>
                  <p className="mt-3 text-sm leading-6 text-gray-400">
                    Let&apos;s get you set up. You&apos;ll create an
                    organization, a workspace, and your first project in just
                    a few steps.
                  </p>
                  <div className="mt-6 grid gap-2 text-left text-xs text-gray-500">
                    <div className="flex items-center gap-2 rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2">
                      <Building2 className="h-3.5 w-3.5 text-violet-400" />
                      Organization — your team or company
                    </div>
                    <div className="flex items-center gap-2 rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2">
                      <Layers className="h-3.5 w-3.5 text-cyan-400" />
                      Workspace — group related projects
                    </div>
                    <div className="flex items-center gap-2 rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2">
                      <FolderOpen className="h-3.5 w-3.5 text-emerald-400" />
                      Project — your research context
                    </div>
                  </div>
                </div>
              )}

              {step === 1 && (
                <div>
                  <h2 className="text-lg font-semibold text-white">
                    Create your organization
                  </h2>
                  <p className="mt-2 text-sm text-gray-400">
                    This could be your company, team, or personal research
                    hub.
                  </p>
                  <div className="mt-6 space-y-4">
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-gray-400">
                        Organization name <span className="text-rose-400">*</span>
                      </label>
                      <input
                        value={orgName}
                        onChange={(e) => {
                          setOrgName(e.target.value);
                          if (!orgSlug || orgSlug === slugify(orgName))
                            setOrgSlug(slugify(e.target.value));
                        }}
                        placeholder="e.g. Acme Corp"
                        className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2.5 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06]"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-gray-400">
                        URL slug
                      </label>
                      <div className="relative">
                        <Hash className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                        <input
                          value={orgSlug}
                          onChange={(e) => setOrgSlug(slugify(e.target.value))}
                          placeholder="acme-corp"
                          className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-3 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06]"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {step === 2 && (
                <div>
                  <h2 className="text-lg font-semibold text-white">
                    Create your workspace
                  </h2>
                  <p className="mt-2 text-sm text-gray-400">
                    Group your projects into workspaces (e.g. Engineering,
                    Marketing, Research).
                  </p>
                  <div className="mt-6 space-y-4">
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-gray-400">
                        Workspace name <span className="text-rose-400">*</span>
                      </label>
                      <input
                        value={wsName}
                        onChange={(e) => {
                          setWsName(e.target.value);
                          if (!wsSlug || wsSlug === slugify(wsName))
                            setWsSlug(slugify(e.target.value));
                        }}
                        placeholder="e.g. General"
                        className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2.5 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06]"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-gray-400">
                        URL slug
                      </label>
                      <div className="relative">
                        <Hash className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                        <input
                          value={wsSlug}
                          onChange={(e) => setWsSlug(slugify(e.target.value))}
                          placeholder="general"
                          className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-3 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06]"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {step === 3 && (
                <div>
                  <h2 className="text-lg font-semibold text-white">
                    Create your first project
                  </h2>
                  <p className="mt-2 text-sm text-gray-400">
                    A project holds your research conversations, documents,
                    and settings.
                  </p>
                  <div className="mt-6 space-y-4">
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-gray-400">
                        Project name <span className="text-rose-400">*</span>
                      </label>
                      <input
                        value={projectName}
                        onChange={(e) => {
                          setProjectName(e.target.value);
                          if (!projectSlug || projectSlug === slugify(projectName))
                            setProjectSlug(slugify(e.target.value));
                        }}
                        placeholder="e.g. Default Project"
                        className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2.5 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06]"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-gray-400">
                        URL slug
                      </label>
                      <div className="relative">
                        <Hash className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                        <input
                          value={projectSlug}
                          onChange={(e) => setProjectSlug(slugify(e.target.value))}
                          placeholder="default"
                          className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] py-2.5 pl-10 pr-3 text-sm text-white placeholder-gray-500 outline-none transition-colors focus:border-violet-500/50 focus:bg-white/[0.06]"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {step === 4 && (
                <div className="text-center">
                  <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-400/20 bg-emerald-500/10 text-emerald-300">
                    <CheckCircle2 className="h-6 w-6" />
                  </span>
                  <h1 className="mt-6 text-xl font-semibold text-white">
                    You&apos;re all set!
                  </h1>
                  <p className="mt-3 text-sm leading-6 text-gray-400">
                    Your organization, workspace, and project are ready. Time
                    to start researching.
                  </p>
                  <div className="mt-6 space-y-2 text-left text-xs text-gray-500">
                    <div className="flex items-center gap-2 rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2">
                      <Building2 className="h-3.5 w-3.5 text-violet-400" />
                      <span>{orgName}</span>
                    </div>
                    <div className="flex items-center gap-2 rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2">
                      <Layers className="h-3.5 w-3.5 text-cyan-400" />
                      <span>{wsName}</span>
                    </div>
                    <div className="flex items-center gap-2 rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2">
                      <FolderOpen className="h-3.5 w-3.5 text-emerald-400" />
                      <span>{projectName}</span>
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          {error && (
            <motion.p
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="mt-4 text-xs text-rose-400"
            >
              {error}
            </motion.p>
          )}

          <div className="mt-8 flex items-center justify-between">
            <button
              onClick={handleBack}
              disabled={step === 0 || loading}
              className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs text-gray-400 transition-colors hover:text-gray-200 disabled:opacity-30"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back
            </button>
            <button
              onClick={handleNext}
              disabled={!canAdvance() || loading}
              className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-cyan-600 px-5 py-2.5 text-sm font-medium text-white transition-all hover:opacity-90 disabled:opacity-40"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : isLastStep ? (
                <>
                  Go to workspace
                  <ArrowRight className="h-4 w-4" />
                </>
              ) : (
                <>
                  Continue
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
