import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  api,
  DEFAULT_TIMEOUT_MS,
  getRefreshToken,
  getTenantIds,
  getToken,
  MAX_RETRIES,
  ORG_ID_KEY,
  PROJECT_ID_KEY,
  REFRESH_KEY,
  RESEARCH_TIMEOUT_MS,
  setToken,
  STREAM_TIMEOUT_MS,
  TOKEN_KEY,
  WS_ID_KEY,
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

describe("constants", () => {
  it("exports the configured timeout and retry constants", () => {
    expect(DEFAULT_TIMEOUT_MS).toBe(30_000);
    expect(RESEARCH_TIMEOUT_MS).toBe(180_000);
    expect(STREAM_TIMEOUT_MS).toBe(120_000);
    expect(MAX_RETRIES).toBe(2);
  });
});

describe("token storage", () => {
  it("getToken returns null when nothing is stored", () => {
    expect(getToken()).toBeNull();
  });

  it("setToken persists token to localStorage", () => {
    setToken("abc-123");
    expect(localStorage.getItem(TOKEN_KEY)).toBe("abc-123");
    expect(getToken()).toBe("abc-123");
  });

  it("setToken with null clears token", () => {
    setToken("abc-123");
    setToken(null);
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(getToken()).toBeNull();
  });

  it("getRefreshToken returns the stored refresh token", () => {
    localStorage.setItem(REFRESH_KEY, "rt-999");
    expect(getRefreshToken()).toBe("rt-999");
  });

  it("getTenantIds returns org, workspace and project ids", () => {
    localStorage.setItem(ORG_ID_KEY, "org-1");
    localStorage.setItem(WS_ID_KEY, "ws-2");
    localStorage.setItem(PROJECT_ID_KEY, "proj-3");
    expect(getTenantIds()).toEqual({
      orgId: "org-1",
      wsId: "ws-2",
      projectId: "proj-3",
    });
  });

  it("getTenantIds returns nulls when nothing stored", () => {
    expect(getTenantIds()).toEqual({ orgId: null, wsId: null, projectId: null });
  });
});

describe("request success paths", () => {
  it("GET returns parsed JSON and sets request id header", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [1, 2] }));

    const data = await api.get<{ items: number[] }>("/documents");
    expect(data).toEqual({ items: [1, 2] });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/documents");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>)["X-Request-ID"]).toMatch(
      /^req_/,
    );
  });

  it("POST serializes JSON body and sets content type", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "conv-1" }));

    await api.post("/conversations", { title: "New" });

    const init = fetchMock.mock.calls[0][1];
    expect(init.body).toBe(JSON.stringify({ title: "New" }));
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json",
    );
  });

  it("DELETE does not send a body", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok" }, 204));

    await api.delete("/documents/doc-1");

    const init = fetchMock.mock.calls[0][1];
    expect(init.method).toBe("DELETE");
    expect(init.body).toBeUndefined();
  });

  it("FormData body is sent as-is without content type", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok" }));
    const form = new FormData();
    form.append("file", new Blob(["pdf"]), "paper.pdf");

    await api.post("/documents/upload", form);

    const init = fetchMock.mock.calls[0][1];
    expect(init.body).toBe(form);
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("PATCH sends a JSON body", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "conv-1" }));

    await api.patch("/conversations/conv-1", { title: "Renamed" });

    const init = fetchMock.mock.calls[0][1];
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ title: "Renamed" });
  });
});

describe("request error classification", () => {
  it("404 throws NOT_FOUND with server detail", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Document missing" }, 404));

    await expect(api.get("/documents/missing")).rejects.toMatchObject({
      name: "ApiError",
      code: "NOT_FOUND",
      status: 404,
      message: "Document missing",
      retryable: false,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("401 without a stored token throws UNAUTHORIZED once", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}, 401));

    await expect(api.get("/private")).rejects.toMatchObject({
      code: "UNAUTHORIZED",
      status: 401,
      retryable: false,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("503 retries then throws INTERNAL_ERROR", async () => {
    vi.useFakeTimers();
    fetchMock.mockResolvedValue(jsonResponse({ detail: "down" }, 503));

    const promise = api.get("/down");
    const assertion = expect(promise).rejects.toMatchObject({
      code: "INTERNAL_ERROR",
      status: 503,
      retryable: true,
    });
    await vi.advanceTimersByTimeAsync(1_000);
    await vi.advanceTimersByTimeAsync(2_000);
    await assertion;
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("network failure is classified OFFLINE", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(api.get("/offline")).rejects.toMatchObject({
      code: "OFFLINE",
      status: 0,
      retryable: true,
    });
  });

  it("aborted request is classified ABORTED without retrying", async () => {
    fetchMock.mockRejectedValue(new DOMException("Aborted", "AbortError"));

    await expect(api.get("/slow")).rejects.toMatchObject({
      code: "ABORTED",
      status: 0,
      retryable: false,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("ApiError instances propagate unchanged", async () => {
    const original = new ApiError("custom", "CUSTOM", 418, false);
    fetchMock.mockRejectedValue(original);

    await expect(api.get("/teapot")).rejects.toBe(original);
  });

  it("does not refresh token on 403", async () => {
    localStorage.setItem(TOKEN_KEY, "jwt-token");
    fetchMock.mockResolvedValue(jsonResponse({ detail: "forbidden" }, 403));

    await expect(api.get("/private")).rejects.toMatchObject({
      code: "FORBIDDEN",
      status: 403,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("401 token refresh", () => {
  it("refreshes token and retries with the new token", async () => {
    localStorage.setItem(TOKEN_KEY, "old-token");
    localStorage.setItem(REFRESH_KEY, "rt-999");
    fetchMock
      .mockResolvedValueOnce(jsonResponse({}, 401))
      .mockResolvedValueOnce(jsonResponse({ access_token: "new-token" }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));

    const data = await api.get("/private");
    expect(data).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const [, lastInit] = fetchMock.mock.calls[2];
    expect((lastInit as Record<string, Record<string, string>>).headers.Authorization).toBe(
      "Bearer new-token",
    );
    expect(localStorage.getItem(TOKEN_KEY)).toBe("new-token");
  });

  it("401 with failed refresh throws UNAUTHORIZED after one refresh attempt", async () => {
    localStorage.setItem(TOKEN_KEY, "old-token");
    localStorage.setItem(REFRESH_KEY, "rt-999");
    fetchMock
      .mockResolvedValueOnce(jsonResponse({}, 401))
      .mockResolvedValueOnce(jsonResponse({}, 401));

    await expect(api.get("/private")).rejects.toMatchObject({
      code: "UNAUTHORIZED",
      status: 401,
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("401 with no refresh token throws UNAUTHORIZED without a refresh call", async () => {
    localStorage.setItem(TOKEN_KEY, "old-token");
    fetchMock.mockResolvedValueOnce(jsonResponse({}, 401));

    await expect(api.get("/private")).rejects.toMatchObject({
      code: "UNAUTHORIZED",
      status: 401,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
