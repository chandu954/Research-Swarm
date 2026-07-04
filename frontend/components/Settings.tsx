"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Settings2, ChevronDown, Check, RefreshCw, Puzzle, Key } from "lucide-react";
import type { ProviderSettings } from "@/lib/useSettings";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const OLLAMA_PRESETS: Record<string, string[]> = {
  planner: ["qwen3:14b", "llama3:8b", "qwen3:8b", "gemma3:12b"],
  research: ["llama3:8b", "qwen3:8b", "mistral:7b"],
  document: ["gemma3:12b", "llama3:8b", "nomic-embed-text"],
  answer: ["gemma3:12b", "llama3:8b", "qwen3:14b", "deepseek-r1:8b"],
};

const OPENROUTER_PRESETS: Record<string, string[]> = {
  planner: ["qwen/qwen3-32b", "google/gemini-2.5-pro", "anthropic/claude-3.5-sonnet", "openai/gpt-4o"],
  research: ["google/gemini-2.5-pro", "mistralai/mistral-small-3.2-24b-instruct", "qwen/qwen3-32b"],
  document: ["qwen/qwen3-32b", "google/gemini-2.5-flash", "anthropic/claude-3.5-haiku"],
  answer: ["deepseek/deepseek-r1", "qwen/qwen3-32b", "anthropic/claude-3.5-sonnet", "openai/gpt-4o"],
};

function filterModels(models: string[], role: string): string[] {
  const keywords: Record<string, string[]> = {
    planner: ["qwen", "claude", "gpt", "gemini", "deepseek"],
    research: ["gemini", "flash", "mistral", "qwen", "gpt"],
    document: ["qwen", "gemma", "claude", "haiku", "embed"],
    answer: ["deepseek", "r1", "qwen", "claude", "gpt", "mistral"],
  };
  const kw = keywords[role] || [];
  const scored = models.map((m) => {
    const score = kw.some((k) => m.toLowerCase().includes(k)) ? 1 : 0;
    return { m, score };
  });
  scored.sort((a, b) => b.score - a.score || a.m.localeCompare(b.m));
  return scored.slice(0, 12).map((s) => s.m);
}

function ModelSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>
        {label}
      </label>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all"
        style={{
          backgroundColor: 'var(--surface)',
          border: '1px solid var(--border)',
          color: 'var(--text-primary)',
        }}
      >
        <span className="truncate">{value}</span>
        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`}
          style={{ color: 'var(--text-muted)' }} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="absolute z-50 w-full mt-1 rounded-lg overflow-hidden shadow-xl"
            style={{
              backgroundColor: 'var(--surface)',
              border: '1px solid var(--border)',
            }}
          >
            {options.map((opt) => (
              <button
                key={opt}
                onClick={() => { onChange(opt); setOpen(false); }}
                className="w-full flex items-center justify-between px-3 py-2 text-sm transition-all text-left"
                style={{ color: 'var(--text-primary)' }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--surface-hover)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <span className="truncate">{opt}</span>
                {opt === value && <Check className="w-3.5 h-3.5 text-primary flex-shrink-0 ml-2" />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface SettingsProps {
  open: boolean;
  onClose: () => void;
  settings: ProviderSettings;
  onSettingsChange: (s: ProviderSettings) => void;
}

function useModelList(provider: string) {
  const [models, setModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchModels = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/models`);
      const data = await res.json();
      setModels(data.models || []);
    } catch (e) {
      setError("Failed to load models");
      setModels([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels, provider]);

  return { models, loading, error, refresh: fetchModels };
}

interface PluginInfo {
  name: string;
  configured: boolean;
  actions: string[];
}

function PluginSection() {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [configs, setConfigs] = useState<Record<string, string>>({});
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/plugins`)
      .then((r) => r.json())
      .then(setPlugins)
      .catch(() => {});
  }, []);

  const configure = async (name: string) => {
    try {
      await fetch(`${API_URL}/plugins/${name}/configure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, config: { token: configs[name] || "" } }),
      });
      const res = await fetch(`${API_URL}/plugins`);
      const data = await res.json();
      setPlugins(data);
    } catch {}
  };

  if (plugins.length === 0) return null;

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider mb-2"
        style={{ color: 'var(--text-muted)' }}
      >
        <Puzzle className="w-3 h-3" />
        Integrations
        <ChevronDown className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-2 overflow-hidden"
          >
            {plugins.map((p) => (
              <div
                key={p.name}
                className="rounded-lg p-3"
                style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium capitalize" style={{ color: 'var(--text-primary)' }}>
                    {p.name}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded ${p.configured ? 'bg-green-500/10 text-green-400' : 'bg-yellow-500/10 text-yellow-400'}`}
                  >
                    {p.configured ? "Connected" : "Not configured"}
                  </span>
                </div>

                {!p.configured && (
                  <div className="flex gap-1.5 mt-2">
                    <input
                      type="password"
                      placeholder="API Key"
                      value={configs[p.name] || ""}
                      onChange={(e) => setConfigs((prev) => ({ ...prev, [p.name]: e.target.value }))}
                      className="flex-1 text-[11px] px-2 py-1.5 rounded"
                      style={{
                        backgroundColor: 'var(--surface)',
                        border: '1px solid var(--border)',
                        color: 'var(--text-primary)',
                      }}
                    />
                    <button
                      onClick={() => configure(p.name)}
                      className="px-2 py-1.5 rounded text-[11px] font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                    >
                      <Key className="w-3 h-3" />
                    </button>
                  </div>
                )}

                {p.actions.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {p.actions.map((a) => (
                      <span
                        key={a}
                        className="text-[9px] px-1.5 py-0.5 rounded"
                        style={{ backgroundColor: 'var(--surface-hover)', color: 'var(--text-muted)' }}
                      >
                        {a}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function Settings({ open, onClose, settings, onSettingsChange }: SettingsProps) {
  const { models: allModels, loading: modelsLoading, refresh: refreshModels } = useModelList(
    settings.provider
  );

  const dynamicModels: Record<string, string[]> = {};
  if (allModels.length > 0) {
    if (settings.provider === "openrouter") {
      for (const role of ["planner", "research", "document", "answer"]) {
        dynamicModels[role] = filterModels(allModels, role);
      }
    } else {
      for (const role of ["planner", "research", "document", "answer"]) {
        dynamicModels[role] = allModels;
      }
    }
  }

  const hasDynamic = allModels.length > 0;
  const presets = settings.provider === "ollama" ? OLLAMA_PRESETS : OPENROUTER_PRESETS;
  const optionsFor = (role: string) =>
    hasDynamic ? dynamicModels[role] : presets[role] || [];

  const update = (partial: Partial<ProviderSettings>) => {
    onSettingsChange({ ...settings, ...partial });
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40"
            style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
          />
          <motion.div
            initial={{ opacity: 0, x: 300 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 300 }}
            className="fixed right-0 top-0 bottom-0 w-[380px] z-50 overflow-y-auto"
            style={{
              backgroundColor: 'var(--surface)',
              borderLeft: '1px solid var(--border)',
            }}
          >
            <div className="p-5">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                  <Settings2 className="w-5 h-5 text-primary" />
                  <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Settings
                  </h2>
                </div>
                <button
                  onClick={onClose}
                  className="p-2 rounded-lg hover:bg-surface-hover transition-colors"
                  style={{ color: 'var(--text-muted)' }}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-6">
                <div>
                  <label className="block text-xs font-medium mb-2" style={{ color: 'var(--text-muted)' }}>
                    LLM Provider
                  </label>
                  <div className="flex gap-2">
                    {(["ollama", "openrouter"] as const).map((p) => (
                      <button
                        key={p}
                        onClick={() => update({
                          provider: p,
                          plannerModel: p === "ollama" ? "qwen3:14b" : "qwen/qwen3-32b",
                          researchModel: p === "ollama" ? "llama3:8b" : "google/gemini-2.5-pro",
                          documentModel: p === "ollama" ? "gemma3:12b" : "qwen/qwen3-32b",
                          answerModel: p === "ollama" ? "gemma3:12b" : "deepseek/deepseek-r1",
                        })}
                        className="flex-1 py-3 rounded-xl text-sm font-medium transition-all"
                        style={{
                          backgroundColor: settings.provider === p
                            ? 'color-mix(in srgb, #6366f1 15%, var(--surface))'
                            : 'var(--surface)',
                          border: `1px solid ${
                            settings.provider === p
                              ? 'color-mix(in srgb, #6366f1 40%, transparent)'
                              : 'var(--border)'
                          }`,
                          color: settings.provider === p ? '#818cf8' : 'var(--text-secondary)',
                        }}
                      >
                        <span className="capitalize">{p}</span>
                        <span className="block text-[10px] mt-0.5 opacity-60">
                          {p === "ollama" ? "Local" : "Cloud"}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                {settings.provider === "openrouter" && (
                  <div>
                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>
                      OpenRouter API Key
                    </label>
                    <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                      Configured via <code className="text-primary">OPENROUTER_API_KEY</code> on the server.
                    </p>
                  </div>
                )}

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                      Model Routing
                    </p>
                    <button
                      onClick={refreshModels}
                      className="p-1 rounded transition-colors"
                      style={{ color: 'var(--text-muted)' }}
                      title="Refresh model list"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${modelsLoading ? 'animate-spin' : ''}`} />
                    </button>
                  </div>
                  <ModelSelect
                    label="Planner"
                    value={settings.plannerModel}
                    options={optionsFor("planner")}
                    onChange={(v) => update({ plannerModel: v })}
                  />
                  <ModelSelect
                    label="Web Research"
                    value={settings.researchModel}
                    options={optionsFor("research")}
                    onChange={(v) => update({ researchModel: v })}
                  />
                  <ModelSelect
                    label="Document Analysis"
                    value={settings.documentModel}
                    options={optionsFor("document")}
                    onChange={(v) => update({ documentModel: v })}
                  />
                  <ModelSelect
                    label="Answer Synthesis"
                    value={settings.answerModel}
                    options={optionsFor("answer")}
                    onChange={(v) => update({ answerModel: v })}
                  />
                </div>

                <PluginSection />
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
