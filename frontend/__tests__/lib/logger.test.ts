import { afterEach, describe, expect, it, vi } from "vitest";

import { createLogger, setLogSink, type LogEntry } from "@/lib/logger";

const entries: LogEntry[] = [];

afterEach(() => {
  entries.length = 0;
  setLogSink(null);
  vi.restoreAllMocks();
});

describe("logger", () => {
  it("emits structured entries through the configured sink", () => {
    setLogSink((entry) => entries.push(entry));
    const log = createLogger("api");

    log.info("Request finished", { status: 200, durationMs: 12 });

    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({
      level: "info",
      message: "Request finished",
      scope: "api",
      context: { status: 200, durationMs: 12 },
    });
    expect(entries[0].timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("serializes Error context without leaking it as [object Object]", () => {
    setLogSink((entry) => entries.push(entry));
    const log = createLogger("workspace");

    log.error("Run failed", { error: new Error("provider exploded") });

    expect(entries[0].context?.error).toMatchObject({
      name: "Error",
      message: "provider exploded",
    });
  });

  it("namespaces child loggers", () => {
    setLogSink((entry) => entries.push(entry));

    createLogger("frontend").child("workspace").child("documents").warn("Slow upload");

    expect(entries[0].scope).toBe("frontend:workspace:documents");
    expect(entries[0].level).toBe("warn");
  });

  it("emits debug entries outside production", () => {
    setLogSink((entry) => entries.push(entry));

    createLogger("verbose").debug("detail");

    expect(entries.map((entry) => entry.message)).toEqual(["detail"]);
  });
});
