import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cancelResearch,
  createApiKey,
  createConversation,
  createOrganization,
  createWorkspace,
  deleteConversation,
  deleteDocument,
  getApiKeys,
  getAuditLogs,
  getDocumentDownloadUrl,
  healthCheck,
  listConversations,
  listDocuments,
  listOrganizations,
  listProjects,
  listWorkspaces,
  loadConversation,
  runResearch,
  updateConversation,
  uploadPDF,
} from "@/lib/api-client";
import { TOKEN_KEY, api } from "@/lib/api-http";

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
  localStorage.setItem(TOKEN_KEY, "jwt-token");
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function lastCall(): [string, RequestInit] {
  const calls = fetchMock.mock.calls as [string, RequestInit][];
  return calls[calls.length - 1];
}

describe("runResearch", () => {
  it("posts the research body with defaults", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ answer: "ok" }));

    await runResearch("What changed?");

    const [url, init] = lastCall();
    expect(url).toBe("http://localhost:8000/research");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      query: "What changed?",
      document_ids: [],
    });
    expect((init.headers as Record<string, string>)["Authorization"]).toBe(
      "Bearer jwt-token",
    );
  });
});

describe("research lifecycle", () => {
  it("cancelResearch posts to the cancel endpoint", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: "cancelled", task_id: "t-1" }));

    await cancelResearch("t-1");

    const [url, init] = lastCall();
    expect(url).toBe("http://localhost:8000/research/t-1/cancel");
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("uploadPDF sends FormData without content type", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ document_id: "d-1" }));
    const file = new File(["pdf"], "paper.pdf", { type: "application/pdf" });

    await uploadPDF(file);

    const [url, init] = lastCall();
    expect(url).toBe("http://localhost:8000/upload");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect(
      (init.headers as Record<string, string>)["Content-Type"],
    ).toBeUndefined();
  });
});

describe("document and conversation wrappers", () => {
  it("listDocuments gets /documents", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await listDocuments();
    expect(lastCall()[0]).toBe("http://localhost:8000/documents");
    expect(lastCall()[1].method).toBe("GET");
  });

  it("listConversations gets /conversations", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await listConversations();
    expect(lastCall()[0]).toBe("http://localhost:8000/conversations");
  });

  it("loadConversation gets /conversations/:id", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "c-1" }));
    await loadConversation("c-1");
    expect(lastCall()[0]).toBe("http://localhost:8000/conversations/c-1");
  });

  it("createConversation posts a default title", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "c-1" }));
    await createConversation();
    const [, init] = lastCall();
    expect(JSON.parse(init.body as string)).toEqual({
      title: "New Conversation",
    });
  });

  it("createConversation posts a custom title", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "c-2" }));
    await createConversation("My Research");
    expect(JSON.parse((lastCall()[1] as RequestInit).body as string)).toEqual({
      title: "My Research",
    });
  });

  it("deleteDocument deletes /documents/:id", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: "deleted" }));
    await deleteDocument("d-1");
    expect(lastCall()[0]).toBe("http://localhost:8000/documents/d-1");
    expect(lastCall()[1].method).toBe("DELETE");
  });

  it("deleteConversation deletes /conversations/:id", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: "deleted" }));
    await deleteConversation("c-1");
    expect(lastCall()[0]).toBe("http://localhost:8000/conversations/c-1");
    expect(lastCall()[1].method).toBe("DELETE");
  });

  it("updateConversation patches /conversations/:id", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "c-1" }));
    await updateConversation("c-1", { title: "Renamed" });
    const [, init] = lastCall();
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ title: "Renamed" });
  });
});

describe("organization, workspace and project wrappers", () => {
  it("listOrganizations gets /organizations", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await listOrganizations();
    expect(lastCall()[0]).toBe("http://localhost:8000/organizations");
  });

  it("createOrganization posts name and slug", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "o-1" }));
    await createOrganization("Acme", "acme");
    const [, init] = lastCall();
    expect(JSON.parse(init.body as string)).toEqual({ name: "Acme", slug: "acme" });
  });

  it("listWorkspaces gets /organizations/:orgId/workspaces", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await listWorkspaces("o-1");
    expect(lastCall()[0]).toBe(
      "http://localhost:8000/organizations/o-1/workspaces",
    );
  });

  it("createWorkspace posts to /organizations/:orgId/workspaces", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "w-1" }));
    await createWorkspace("o-1", "West");
    const [, init] = lastCall();
    expect(JSON.parse(init.body as string)).toEqual({ name: "West" });
  });

  it("listProjects gets nested projects path", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await listProjects("o-1", "w-1");
    expect(lastCall()[0]).toBe(
      "http://localhost:8000/organizations/o-1/workspaces/w-1/projects",
    );
  });
});

describe("api key and audit wrappers", () => {
  it("getApiKeys gets /api-keys", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await getApiKeys();
    expect(lastCall()[0]).toBe("http://localhost:8000/api-keys");
  });

  it("createApiKey posts /api-keys", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "k-1" }));
    await createApiKey("key-1");
    expect(JSON.parse((lastCall()[1] as RequestInit).body as string)).toEqual({
      name: "key-1",
    });
  });

  it("getAuditLogs gets /audit-logs", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await getAuditLogs();
    expect(lastCall()[0]).toBe("http://localhost:8000/audit-logs");
  });
});

describe("health and download url", () => {
  it("healthCheck gets /health", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok" }));
    await healthCheck();
    expect(lastCall()[0]).toBe("http://localhost:8000/health");
  });

  it("getDocumentDownloadUrl prefixes API url to the signed path", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ url: "/documents/d-1/download", expires_in: 300 }));

    const url = await getDocumentDownloadUrl("d-1");
    expect(url).toBe("http://localhost:8000/documents/d-1/download");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
