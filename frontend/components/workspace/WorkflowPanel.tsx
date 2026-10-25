"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";

import AgentLogs from "@/components/AgentLogs";
import ExecutionTimeline from "@/components/ExecutionTimeline";
import MetricsPanel from "@/components/MetricsPanel";
import PDFUploader from "@/components/PDFUploader";
import ReportsPanel from "@/components/ReportsPanel";
import Sources from "@/components/Sources";
import WorkflowOverview from "@/components/WorkflowOverview";
import { KnowledgeGraphSkeleton } from "@/components/Skeletons";
import { useElapsed } from "@/lib/useElapsed";
import type { ResearchWorkspaceController } from "@/lib/useResearchWorkspace";

const KnowledgeGraph = dynamic(() => import("@/components/KnowledgeGraph"), {
  ssr: false,
  loading: () => <KnowledgeGraphSkeleton />,
});

// Self-contained elapsed timer for the workflow header. Owns its own 250ms
// tick so the rest of the workspace tree is never re-rendered while running.
function ResearchProgressTimer() {
  const elapsed = useElapsed(true);
  return (
    <div className="mt-2.5 flex items-center justify-between text-[10px] text-[var(--text-muted)]">
      <span>Research in progress</span>
      <span className="font-mono">{Math.floor(elapsed)}s</span>
    </div>
  );
}

export default function WorkflowPanel({
  workspace,
}: {
  workspace: ResearchWorkspaceController;
}) {
  const {
    phase,
    isRunning,
    mergedLogs,
    mergedAgentMetrics,
    mergedExecutionTime,
    mergedSourceCount,
    selectedDocs,
    sources,
    plan,
    lastAnswer,
    mergedDocuments,
    setDocuments,
    setSelectedDocs,
    setInspectedSource,
    focusComposer,
    live,
  } = workspace;

  return (
    <aside
      className={`workflow-panel fixed inset-y-0 right-0 z-40 w-[350px] translate-x-full overflow-y-auto xl:static xl:z-auto xl:block xl:translate-x-0 ${
        workspace.workflowOpen ? "!translate-x-0" : ""
      }`}
    >
      <div className="sticky top-0 z-10 border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_88%,transparent)] px-4 py-3 backdrop-blur-lg">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-semibold tracking-tight text-[var(--text-primary)]">
            Workflow
          </p>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--surface-hover)] px-2.5 py-1 text-[9px] font-medium uppercase tracking-[0.08em] text-[var(--text-secondary)]">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                phase === "running"
                  ? "animate-pulse bg-violet-400"
                  : phase === "failed"
                    ? "bg-rose-400"
                    : phase === "completed"
                      ? "bg-emerald-400"
                      : "bg-[var(--text-muted)]"
              }`}
            />
            {phase}
          </span>
        </div>
        {phase === "running" && <ResearchProgressTimer />}
      </div>

      <div className="space-y-5 p-4">
        {phase === "idle" && (
          <div className="unified-panel">
            <WorkflowOverview bare lastSession={live.sessions[0] ?? null} />
            <ReportsPanel
              reports={live.reports}
              onStartResearch={focusComposer}
              bare
            />
            <PDFUploader
              documents={mergedDocuments}
              onDocumentsChange={setDocuments}
              selectedDocs={selectedDocs}
              onSelectionChange={setSelectedDocs}
            />
          </div>
        )}

        {phase === "running" && (
          <div className="unified-panel">
            <ExecutionTimeline
              logs={mergedLogs}
              agentMetrics={mergedAgentMetrics}
              isRunning={isRunning}
            />
            <MetricsPanel
              agentMetrics={mergedAgentMetrics}
              executionTime={mergedExecutionTime}
              sourceCount={mergedSourceCount}
              documentCount={selectedDocs.length}
              lastRun={live.lastMetrics}
            />
            <Sources sources={sources} onInspect={setInspectedSource} />
            <AgentLogs logs={mergedLogs} plan={plan} isRunning={isRunning} />
          </div>
        )}

        {phase === "completed" && (
          <>
            <div className="unified-panel">
              <MetricsPanel
                agentMetrics={mergedAgentMetrics}
                executionTime={mergedExecutionTime}
                sourceCount={mergedSourceCount}
                documentCount={selectedDocs.length}
                lastRun={live.lastMetrics}
              />
              <Sources sources={sources} onInspect={setInspectedSource} />
              <ReportsPanel
                reports={live.reports}
                onStartResearch={focusComposer}
                bare
              />
            </div>
            {lastAnswer && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <KnowledgeGraph answer={lastAnswer} sources={sources} />
              </motion.div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
