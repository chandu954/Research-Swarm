import { afterEach, describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useProviderSettings, type ProviderSettings } from "@/lib/useSettings";

const STORAGE_KEY = "researchswarm-provider-settings";

const DEFAULTS: ProviderSettings = {
  provider: "openrouter",
  plannerModel: "qwen/qwen3-32b",
  researchModel: "google/gemini-2.5-flash",
  documentModel: "qwen/qwen3-32b",
  answerModel: "mistralai/mistral-small-3.2-24b-instruct",
};

function clearStorage() {
  localStorage.removeItem(STORAGE_KEY);
}

afterEach(() => {
  clearStorage();
});

describe("useProviderSettings defaults", () => {
  it("returns defaults when nothing is stored", () => {
    const { result } = renderHook(() => useProviderSettings());
    expect(result.current.settings).toEqual(DEFAULTS);
  });

  it("merges stored settings over defaults", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ provider: "ollama", plannerModel: "llama3:8b", researchModel: "llama3:8b" }),
    );
    const { result } = renderHook(() => useProviderSettings());
    expect(result.current.settings.provider).toBe("ollama");
    expect(result.current.settings.plannerModel).toBe("llama3:8b");
    expect(result.current.settings.researchModel).toBe("llama3:8b");
  });

  it("resets to defaults when stored Ollama config has cloud model ids", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        provider: "ollama",
        plannerModel: "qwen/qwen3-32b",
        researchModel: "google/gemini-2.5-flash",
      }),
    );
    const { result } = renderHook(() => useProviderSettings());
    expect(result.current.settings).toEqual(DEFAULTS);
  });

  it("falls back to defaults when stored value is invalid JSON", () => {
    localStorage.setItem(STORAGE_KEY, "{not json");
    const { result } = renderHook(() => useProviderSettings());
    expect(result.current.settings).toEqual(DEFAULTS);
  });
});

describe("update", () => {
  it("persists merged settings to localStorage", () => {
    const { result } = renderHook(() => useProviderSettings());
    act(() => {
      result.current.update({ researchModel: "llama3:8b" });
    });
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) as string)).toEqual({
      ...DEFAULTS,
      researchModel: "llama3:8b",
    });
    expect(result.current.settings.researchModel).toBe("llama3:8b");
    expect(result.current.settings.provider).toBe(DEFAULTS.provider);
  });
});
