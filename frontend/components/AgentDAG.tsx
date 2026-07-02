"use client";

import { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  NodeProps,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  AlertCircle,
  Loader2,
  Clock,
} from "lucide-react";
import type { AgentLog } from "@/lib/types";
import { AGENT_MAP, AGENT_ORDER, colorStyles } from "@/lib/agents";
import { cn } from "@/lib/utils";

interface AgentNodeData {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  gradient: string;
  status: string;
  duration: number | null;
  color: string;
}

interface AgentDAGProps {
  logs: AgentLog[];
  isRunning: boolean;
  onInspect: (agentKey: string) => void;
}

function getAgentStatus(key: string, logs: AgentLog[], isRunning: boolean) {
  const agentLogs = logs.filter((l) => l.agent === key);
  if (agentLogs.length === 0) return "pending";
  const last = agentLogs[agentLogs.length - 1];
  if (last.status === "completed") return "completed";
  if (last.status === "failed") return "failed";
  return "running";
}

function getAgentDuration(key: string, logs: AgentLog[]): number | null {
  const agentLogs = logs.filter((l) => l.agent === key);
  if (agentLogs.length < 2) return null;
  return agentLogs[agentLogs.length - 1].timestamp - agentLogs[0].timestamp;
}

function AgentNode({ data }: NodeProps) {
  const { label, icon: Icon, gradient, status, duration } = data as unknown as AgentNodeData;
  return (
    <motion.div
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "relative flex items-center gap-3 rounded-xl border px-4 py-3 shadow-lg backdrop-blur-sm transition-all",
        status === "completed" && "border-emerald-400/30 bg-emerald-500/[0.08] shadow-emerald-500/10",
        status === "running" && "border-cyan-400/30 bg-cyan-500/[0.08] shadow-cyan-500/10",
        status === "failed" && "border-rose-400/30 bg-rose-500/[0.08] shadow-rose-500/10",
        status === "pending" && "border-white/[0.06] bg-white/[0.03]",
      )}
      style={{ minWidth: 160 }}
    >
      <Handle type="target" position={Position.Top} className="!border-white/[0.08] !bg-white/[0.04]" />
      <span
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br text-xs font-bold text-white shadow-sm",
          gradient,
        )}
      >
        {Icon ? <Icon className="h-4 w-4" /> : "?"}
      </span>
      <div className="flex-1">
        <p className={cn(
          "text-xs font-semibold",
          status === "pending" ? "text-[var(--text-muted)]" : "text-[var(--text-primary)]"
        )}>
          {label}
        </p>
        <div className="mt-0.5 flex items-center gap-1.5">
          {status === "completed" ? (
            <CheckCircle2 className="h-3 w-3 text-emerald-400" />
          ) : status === "running" ? (
            <Loader2 className="h-3 w-3 animate-spin text-cyan-400" />
          ) : status === "failed" ? (
            <AlertCircle className="h-3 w-3 text-rose-400" />
          ) : (
            <Clock className="h-3 w-3 text-[var(--text-muted)]" />
          )}
          <span className="text-[9px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {status}
          </span>
          {duration !== null && (
            <span className="text-[9px] tabular-nums text-[var(--text-muted)] opacity-60">
              {duration < 1 ? `${Math.round(duration * 1000)}ms` : `${duration.toFixed(1)}s`}
            </span>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!border-white/[0.08] !bg-white/[0.04]" />
    </motion.div>
  );
}

const nodeTypes = { agent: AgentNode as any };

export default function AgentDAG({ logs, isRunning, onInspect }: AgentDAGProps) {
  const initialNodes: Node[] = useMemo(
    () =>
      AGENT_ORDER.map((key, i) => {
        const config = AGENT_MAP[key];
        const status = getAgentStatus(key, logs, isRunning);
        const duration = getAgentDuration(key, logs);
        return {
          id: key,
          type: "agent",
          position: { x: 0, y: i * 140 },
          data: {
            label: config?.label || key,
            icon: config?.icon,
            gradient: config?.gradient,
            color: config?.color,
            status,
            duration,
          },
          draggable: true,
        };
      }),
    [logs, isRunning],
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      AGENT_ORDER.slice(0, -1).map((key, i) => ({
        id: `${key}-${AGENT_ORDER[i + 1]}`,
        source: key,
        target: AGENT_ORDER[i + 1],
        animated: isRunning && getAgentStatus(key, logs, isRunning) === "completed",
        style: {
          stroke: "rgba(255,255,255,0.1)",
          strokeWidth: 1.5,
        },
        activeStyle: {
          stroke: "rgba(6, 182, 212, 0.5)",
          strokeWidth: 2,
        },
      })),
    [logs, isRunning],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onInspect(node.id);
    },
    [onInspect],
  );

  return (
    <div className="h-[500px] w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        minZoom={0.5}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{
          style: { stroke: "rgba(255,255,255,0.08)", strokeWidth: 1.5 },
          animated: false,
        }}
        className="rounded-xl border border-white/[0.06] bg-[var(--bg)]"
      >
        <Background color="rgba(255,255,255,0.03)" gap={24} />
        <Controls
          className="!border-white/[0.06] !bg-white/[0.04] !text-[var(--text-muted)] [&>button]:!border-white/[0.06] [&>button]:!bg-transparent [&>button]:!text-[var(--text-muted)] hover:[&>button]:!bg-white/[0.06]"
        />
        <MiniMap
          nodeColor="rgba(255,255,255,0.08)"
          maskColor="rgba(0,0,0,0.6)"
          className="!border-white/[0.06] !bg-[var(--bg)]"
        />
      </ReactFlow>
    </div>
  );
}
