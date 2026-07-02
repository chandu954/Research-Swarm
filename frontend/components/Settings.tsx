"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Settings2, ChevronDown, Check, RefreshCw } from "lucide-react";
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
                    <input
                      type="password"
                      value={settings.openrouterKey}
                      onChange={(e) => update({ openrouterKey: e.target.value })}
                      placeholder="sk-or-v1-..."
                      className="input-field w-full text-sm"
                    />
                    <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
                      Get your key at{" "}
                      <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer"
                         className="text-primary hover:underline">openrouter.ai/keys</a>
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
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
