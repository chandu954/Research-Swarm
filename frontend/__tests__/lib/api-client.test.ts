import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { checkHealth, cancelResearch, runResearch, subscribeResearchLogs } from "@/lib/api-client";
import {
  ORG_ID_KEY,
  TOKEN_KEY,
  WS_ID_KEY,
  api,
} from "@/lib/api-http";
import { ApiError } from "@/lib/api-errors";

type MockResponse = {
  ok: boolean;
  status: number;
  text: () => Promise<string>;
  json: () => Promise<unknown>;
};

function jsonResponse(data: unknown, status = 200): MockResponse {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(JSON.stringify(data)),
    json: () => Promise.resolve(data),
  };
}

function emptyResponse(status = 204): MockResponse {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(""),
    json: () => Promise.resolve(undefined),
  };
}

const fetchMock = vi.fn();

beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("api request", () => {
  it("returns parsed JSON from a successful response", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [1, 2] }));

    await expect(api.get<{ items: number[] }>("/documents")).resolves.toEqual({
      items: [1, 2],
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/documents");
    expect(init.method).toBe("GET");
  });

  it("returns null for an empty success response", async () => {
    fetchMock.mockResolvedValue(emptyResponse());

    await expect(api.delete("/documents/doc-1")).resolves.toBeNull();
  });

  it("sends auth and tenant headers when present", async () => {
    localStorage.setItem(TOKEN_KEY, "jwt-token");
    localStorage.setItem(ORG_ID_KEY, "org-1");
    localStorage.setItem(WS_ID_KEY, "ws-1");
    fetchMock.mockResolvedValue(jsonResponse({}));

    await api.get("/conversations");

    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer jwt-token");
    expect(headers["X-Organization-Id"]).toBe("org-1");
    expect(headers["X-Workspace-Id"]).toBe("ws-1");
    expect(headers["X-Request-ID"]).toMatch(/^req_/);
  });

  it("does not set Content-Type for FormData bodies", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok" }));
    const form = new FormData();
    form.append("file", new Blob(["pdf"]), "paper.pdf");

    await api.post("/documents/upload", form);

    const init = fetchMock.mock.calls[0][1];
    expect(init.body).toBe(form);
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("serializes JSON bodies for POST requests", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "conv-1" }));

    await api.post("/conversations", { title: "New" });

    const init = fetchMock.mock.calls[0][1];
    expect(init.body).toBe(JSON.stringify({ title: "New" }));
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json",
    );
  });

  it("uses the server-provided detail for 404 responses", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Document missing" }, 404));

    await expect(api.get("/documents/missing", { retryable: false })).rejects.toMatchObject({
      name: "ApiError",
      code: "NOT_FOUND",
      status: 404,
      message: "Document missing",
    });
  });

  it("does not retry unauthorized responses", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}, 401));

    await expect(api.get("/private")).rejects.toMatchObject({
      code: "UNAUTHORIZED",
      retryable: false,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("retries retryable server errors with backoff", async () => {
    vi.useFakeTimers();
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: "temporary" }, 500))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));

    const promise = api.get("/flaky");
    await vi.advanceTimersByTimeAsync(1_000);

    await expect(promise).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("throws the classified error after exhausting retries", async () => {
    vi.useFakeTimers();
    fetchMock.mockResolvedValue(jsonResponse({ detail: "down" }, 503));

    const promise = api.get("/down");
    const assertion = expect(promise).rejects.toMatchObject({
      code: "INTERNAL_ERROR",
      status: 503,
    });
    await vi.advanceTimersByTimeAsync(1_000);
    await vi.advanceTimersByTimeAsync(2_000);
    await assertion;
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("classifies aborted requests as ABORTED without retrying", async () => {
    fetchMock.mockRejectedValue(new DOMException("Aborted", "AbortError"));

    await expect(api.get("/slow", { retryable: false })).rejects.toMatchObject({
      code: "ABORTED",
      retryable: false,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("classifies network failures as OFFLINE", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(api.get("/offline", { retryable: false })).rejects.toMatchObject({
      code: "OFFLINE",
      retryable: true,
    });
  });

  it("propagates ApiError instances unchanged", async () => {
    const original = new ApiError("custom", "CUSTOM", 418, false);
    fetchMock.mockRejectedValue(original);

    await expect(api.get("/teapot", { retryable: false })).rejects.toBe(original);
  });
});

describe("checkHealth", () => {
  it("reports healthy responses", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status: "healthy" }),
    });

    await expect(checkHealth()).resolves.toEqual({ ok: true, status: "healthy" });
  });

  it("reports the HTTP status when the health endpoint fails", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ detail: "starting" }),
    });

    await expect(checkHealth()).resolves.toEqual({
      ok: false,
      status: "HTTP 503",
      detail: "starting",
    });
  });

  it("reports offline when the request throws", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    const result = await checkHealth();
    expect(result.ok).toBe(false);
    expect(result.status).toBe("offline");
    expect(result.detail).toContain("Failed to fetch");
  });
});

describe("runResearch", () => {
  it("posts the query, documents, provider settings and debate flag", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ answer: "ok" }));

    await runResearch(
      "What changed?",
      ["doc-1"],
      {
        provider: "openrouter",
        plannerModel: "planner",
        researchModel: "researcher",
        documentModel: "documents",
        answerModel: "answer",
      },
      "task-1",
      "conv-1",
      true,
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/research");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      query: "What changed?",
      document_ids: ["doc-1"],
      stream_task_id: "task-1",
      conversation_id: "conv-1",
      debate_mode: true,
      llm_provider: "openrouter",
      planner_model: "planner",
      research_model: "researcher",
      document_model: "documents",
      answer_model: "answer",
    });
  });

  it("runResearch omits optional fields when not provided", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ answer: "ok" }));

    await runResearch("Hello");

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).toEqual({ query: "Hello", document_ids: [] });
    expect(body.stream_task_id).toBeUndefined();
    expect(body.conversation_id).toBeUndefined();
    expect(body.debate_mode).toBeUndefined();
  });
});

describe("cancelResearch", () => {
  it("posts to the cancel endpoint with task id and timeout", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: "cancelled", task_id: "t-1" }));

    await cancelResearch("t-1");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/research/t-1/cancel");
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
    expect(init.timeout).toBe(10_000);
  });
});

describe("subscribeResearchLogs", () => {
  it("streams log events and calls callbacks", async () => {
    const encoder = new TextEncoder();
    const reader = {
      read: vi.fn()
        .mockResolvedValueOnce({
          done: false,
          value: encoder.encode(
            "event: log\ndata: {\"agent\":\"researcher\",\"action\":\"started\"}\n",
          ),
        })
        .mockResolvedValueOnce({ done: true, value: null }),
      releaseLock: vi.fn(),
    };
    fetchMock.mockResolvedValue({
      ok: true,
      body: { getReader: () => reader },
    } as unknown as Response);

    const onLog = vi.fn();
    const onDone = vi.fn();
    const controller = subscribeResearchLogs("task-1", { onLog, onDone });

    await new Promise((r) => setTimeout(r, 100));

    expect(onLog).toHaveBeenCalledWith(
      expect.objectContaining({ agent: "researcher", action: "started" }),
    );
    expect(onDone).toHaveBeenCalledTimes(1);
    controller.abort();
  });

  it("calls onError when the stream response is not ok", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: "stream failed" }),
    } as unknown as Response);

    const onError = vi.fn();
    const controller = subscribeResearchLogs("task-1", { onError });

    await new Promise((r) => setTimeout(r, 50));

    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ status: 500 }),
    );
    controller.abort();
  });

  it("aborts on AbortError without calling onError", async () => {
    fetchMock.mockRejectedValue(new DOMException("Aborted", "AbortError"));

    const onError = vi.fn();
    const controller = subscribeResearchLogs("task-1", { onError });

    await new Promise((r) => setTimeout(r, 50));

    expect(onError).not.toHaveBeenCalled();
  });
});
