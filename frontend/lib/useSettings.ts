"use client";

import { useState, useCallback } from "react";

export interface ProviderSettings {
  provider: "ollama" | "openrouter";
  plannerModel: string;
  researchModel: string;
  documentModel: string;
  answerModel: string;
  openrouterKey: string;
}

const STORAGE_KEY = "researchswarm-provider-settings";

const DEFAULTS: ProviderSettings = {
  provider: "openrouter",
  plannerModel: "qwen/qwen3-32b",
  researchModel: "google/gemini-2.5-flash",
  documentModel: "qwen/qwen3-32b",
  answerModel: "mistralai/mistral-small-3.2-24b-instruct",
  openrouterKey: "",
};

function loadFromStorage(): ProviderSettings {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      const merged = { ...DEFAULTS, ...parsed };
      // Reset stale Ollama config when cloud model ids are stored
      if (
        merged.provider === "ollama" &&
        (merged.plannerModel?.includes("/") || merged.researchModel?.includes("/"))
      ) {
        return DEFAULTS;
      }
      return merged;
    }
  } catch {}
  return DEFAULTS;
}

function saveToStorage(settings: ProviderSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {}
}

export function useProviderSettings() {
  const [settings, setSettings] = useState<ProviderSettings>(loadFromStorage);

  const update = useCallback((partial: Partial<ProviderSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...partial };
      saveToStorage(next);
      return next;
    });
  }, []);

  return { settings, update };
}
