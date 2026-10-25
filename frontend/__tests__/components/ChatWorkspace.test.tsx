import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-errors";
import { useResearchWorkspace } from "@/lib/useResearchWorkspace";
import type { ResearchResult } from "@/lib/types";

const apiMocks = vi.hoisted(() => ({
  listDocuments: vi.fn(),
  runResearch: vi.fn(),
  cancelResearch: vi.fn(),
  subscribeResearchLogs: vi.fn(),
  uploadPDF: vi.fn(),
  loadConversation: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const { ApiError } = await import("@/lib/api-errors");
  return {
    ApiClientError: ApiError,
    ...apiMocks,
  };
});

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "user-1" }, token: "jwt-token" }),
}));

vi.mock("@/lib/useSettings", () => ({
  useProviderSettings: () => ({
    settings: {
      provider: "openrouter",
      plannerModel: "planner",
      researchModel: "researcher",
      documentModel: "documents",
      answerModel: "answer",
    },
    update: vi.fn(),
  }),
}));

vi.mock("@/lib/tenant", () => ({
  useTenant: () => ({ currentWorkspace: { id: "ws-1", name: "Workspace" } }),
}));

vi.mock("@/lib/websocket", () => ({
  collaborationClient: { connect: vi.fn(), disconnect: vi.fn() },
}));

const liveWorkspace = {
  documents: [] as Array<{ id: string; name: string; size_bytes: number; status: string; pages?: number }>,
  collections: [],
  sessions: [],
  reports: [],
  lastMetrics: null,
  refresh: vi.fn(),
};

vi.mock("@/lib/supabase/query", () => ({
  useLiveWorkspace: () => liveWorkspace,
}));

vi.mock("@/lib/supabase/realtime", () => ({
  useRealtimeWorkspace: () => ({
    agentMetrics: {},
    agentLogs: [],
    documents: [],
    executionTimeMs: null,
    sourcesFound: 0,
  }),
}));

function researchResult(overrides: Partial<ResearchResult> = {}): ResearchResult {
  return {
    task_id: "task-1",
    query: "What is new?",
    answer: "A cited answer.",
    sources: [],
    plan: [],
    logs: [],
    status: "completed",
    errors: [],
    execution_time: 1.2,
    ...overrides,
  } as ResearchResult;
}

beforeEach(() => {
  vi.clearAllMocks();
  liveWorkspace.documents = [];
  liveWorkspace.collections = [];
  liveWorkspace.sessions = [];
  liveWorkspace.reports = [];
  liveWorkspace.lastMetrics = null;
  apiMocks.listDocuments.mockResolvedValue([]);
  apiMocks.subscribeResearchLogs.mockReturnValue(new AbortController());
  apiMocks.cancelResearch.mockResolvedValue({ status: "cancelled", task_id: "task-1" });
  apiMocks.uploadPDF.mockResolvedValue({
    document_id: "doc-1",
    filename: "paper.pdf",
    size: 10,
    status: "ready",
  });
});

describe("useResearchWorkspace", () => {
  it("starts idle and loads existing documents", async () => {
    apiMocks.listDocuments.mockResolvedValue([
      {
        id: "doc-1",
        filename: "paper.pdf",
        size_bytes: 42,
        status: "ready",
        page_count: 3,
      },
    ]);

    const { result } = renderHook(() => useResearchWorkspace());

    expect(result.current.phase).toBe("idle");
    await waitFor(() => expect(result.current.documents).toHaveLength(1));
    expect(result.current.documents[0]).toMatchObject({
      document_id: "doc-1",
      filename: "paper.pdf",
      size: 42,
      page_count: 3,
    });
  });

  it("runs research and appends the assistant answer", async () => {
    apiMocks.runResearch.mockResolvedValue(researchResult());

    const { result } = renderHook(() => useResearchWorkspace());

    await act(async () => {
      await result.current.handleSend("What is new?");
    });

    expect(apiMocks.runResearch).toHaveBeenCalledWith(
      "What is new?",
      [],
      expect.objectContaining({ provider: "openrouter" }),
      expect.any(String),
      undefined,
      false,
      expect.any(AbortSignal),
    );
    expect(result.current.messages.map((message) => message.role)).toEqual([
      "user",
      "assistant",
    ]);
    expect(result.current.messages[1].content).toBe("A cited answer.");
    expect(result.current.phase).toBe("completed");
    expect(result.current.isRunning).toBe(false);
    expect(result.current.runError).toBeNull();
  });

  it("surfaces a failed run and exposes the retry action", async () => {
    apiMocks.runResearch.mockRejectedValueOnce(
      new ApiError("The backend is unavailable.", "INTERNAL_ERROR", 500, true),
    );

    const { result } = renderHook(() => useResearchWorkspace());

    await act(async () => {
      await result.current.handleSend("What is new?");
    });

    expect(result.current.phase).toBe("failed");
    expect(result.current.runError).toBe("The backend is unavailable.");
    expect(result.current.messages.at(-1)?.content).toContain(
      "The backend is unavailable.",
    );
  });

  it("renders cancellation as an idle message instead of an error", async () => {
    apiMocks.runResearch.mockRejectedValueOnce(
      new ApiError("Request was cancelled.", "ABORTED", 0, false),
    );

    const { result } = renderHook(() => useResearchWorkspace());

    await act(async () => {
      await result.current.handleSend("What is new?");
    });

    expect(result.current.runError).toBeNull();
    expect(result.current.phase).toBe("completed");
    expect(result.current.messages.at(-1)?.content).toContain("Research cancelled.");
  });

  it("retries with the last user query without duplicating it", async () => {
    apiMocks.runResearch
      .mockResolvedValueOnce(researchResult())
      .mockResolvedValueOnce(researchResult({ answer: "Second answer." }));

    const { result } = renderHook(() => useResearchWorkspace());

    await act(async () => {
      await result.current.handleSend("What is new?");
    });

    await act(async () => {
      result.current.handleRetryResearch();
    });

    await waitFor(() => expect(apiMocks.runResearch).toHaveBeenCalledTimes(2));
    expect(apiMocks.runResearch.mock.calls[1][0]).toBe("What is new?");
    await waitFor(() =>
      expect(result.current.messages.at(-1)?.content).toBe("Second answer."),
    );
    expect(
      result.current.messages.filter((message) => message.role === "user"),
    ).toHaveLength(1);
  });

  it("cancels an in-flight research task", async () => {
    let rejectRun: (error: unknown) => void = () => {};
    apiMocks.runResearch.mockReturnValue(
      new Promise((_resolve, reject) => {
        rejectRun = reject;
      }),
    );

    const { result } = renderHook(() => useResearchWorkspace());

    let sendPromise: Promise<void> = Promise.resolve();
    act(() => {
      sendPromise = result.current.handleSend("Long running query");
    });

    await waitFor(() => expect(result.current.isRunning).toBe(true));

    act(() => {
      result.current.handleCancelResearch();
    });

    rejectRun(new ApiError("Request was cancelled.", "ABORTED", 0, false));
    await act(async () => {
      await sendPromise;
    });

    expect(apiMocks.cancelResearch).toHaveBeenCalledWith(expect.any(String));
    expect(result.current.runError).toBeNull();
    expect(result.current.messages.at(-1)?.content).toContain("Research cancelled.");
  });

  it("resets all conversation state on new chat", async () => {
    apiMocks.runResearch.mockResolvedValue(researchResult());
    const { result } = renderHook(() => useResearchWorkspace());

    await act(async () => {
      await result.current.handleSend("What is new?");
    });
    expect(result.current.messages.length).toBeGreaterThan(0);

    act(() => {
      result.current.handleNewChat();
    });

    expect(result.current.messages).toEqual([]);
    expect(result.current.sources).toEqual([]);
    expect(result.current.plan).toEqual([]);
    expect(result.current.phase).toBe("idle");
  });

  it("adds uploaded documents to the workspace", async () => {
    const { result } = renderHook(() => useResearchWorkspace());
    const file = new File(["pdf"], "paper.pdf", { type: "application/pdf" });

    await act(async () => {
      result.current.handleDocumentUpload([file] as unknown as FileList);
      await Promise.resolve();
    });

    await waitFor(() => expect(result.current.documents).toHaveLength(1));
    expect(result.current.documents[0].document_id).toBe("doc-1");
  });

  it("loads a saved conversation and maps message ids, timestamps, and sources", async () => {
    apiMocks.loadConversation.mockResolvedValueOnce({
      messages: [
        { message_id: "saved-1", role: "user", content: "Saved question", timestamp: 123 },
        { id: "saved-2", role: "assistant", content: "Saved answer", sources: [{ title: "Source" }] },
      ],
    });
    const { result } = renderHook(() => useResearchWorkspace());

    await act(async () => result.current.handleSelectConversation("conversation-1"));

    expect(apiMocks.loadConversation).toHaveBeenCalledWith("conversation-1");
    expect(result.current.conversationId).toBe("conversation-1");
    expect(result.current.messages).toMatchObject([
      { id: "saved-1", role: "user", content: "Saved question", timestamp: 123, sources: [] },
      { id: "saved-2", role: "assistant", content: "Saved answer", sources: [{ title: "Source" }] },
    ]);
    expect(result.current.query).toBe("Saved question");
    expect(result.current.lastAnswer).toBe("Saved answer");
  });

  it("clears selection and loaded documents when clearing the workspace", async () => {
    apiMocks.listDocuments.mockResolvedValueOnce([
      { id: "doc-1", filename: "paper.pdf", size_bytes: 10, status: "ready" },
    ]);
    const { result } = renderHook(() => useResearchWorkspace());
    await waitFor(() => expect(result.current.documents).toHaveLength(1));
    act(() => result.current.setSelectedDocs(["doc-1"]));

    await act(async () => result.current.handleClearAll());

    expect(result.current.documents).toEqual([]);
    expect(result.current.selectedDocs).toEqual([]);
    expect(result.current.messages).toEqual([]);
    expect(result.current.phase).toBe("idle");
  });

  it("does not add an answerless result as a successful response", async () => {
    apiMocks.runResearch.mockResolvedValueOnce(researchResult({ answer: "  ", errors: ["No evidence"] }));
    const { result } = renderHook(() => useResearchWorkspace());

    await act(async () => result.current.handleSend("Question without answer"));

    expect(result.current.phase).toBe("failed");
    expect(result.current.runError).toBe("No evidence");
    expect(result.current.messages.at(-1)?.content).toContain("No evidence");
    expect(result.current.messages.some((message) => message.content === "Thinking...")).toBe(false);
  });

  it("merges realtime documents and preserves completed response logs", async () => {
    liveWorkspace.documents = [
      { id: "live-doc", name: "live.pdf", size_bytes: 5, status: "ready", pages: 2 },
    ];
    const { result, rerender } = renderHook(() => useResearchWorkspace());
    await waitFor(() => expect(result.current.mergedDocuments).toEqual([
      expect.objectContaining({ document_id: "live-doc", filename: "live.pdf", page_count: 2 }),
    ]));

    apiMocks.runResearch.mockResolvedValueOnce(researchResult({
      logs: [{ agent: "planner", action: "plan", status: "completed", timestamp: 1 }],
    }));
    await act(async () => result.current.handleSend("merge test"));
    rerender();
    expect(result.current.mergedLogs).toEqual([
      expect.objectContaining({ agent: "planner", action: "plan", status: "completed" }),
    ]);
  });
});
