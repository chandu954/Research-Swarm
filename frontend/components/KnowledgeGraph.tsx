"use client";

import { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { BrainCircuit, Globe2, FileText, Lightbulb, Building2, BookOpen } from "lucide-react";
import type { SourceCitation } from "@/lib/types";
import { buildGraph, type GraphEntity } from "@/lib/knowledge-graph";

const typeIcons: Record<string, React.ElementType> = {
  concept: Lightbulb,
  technology: Globe2,
  company: Building2,
  paper: FileText,
  topic: BookOpen,
};

function EntityNode({ data }: NodeProps) {
  const entity = data.entity as GraphEntity;
  const Icon = typeIcons[entity.type] || BrainCircuit;

  return (
    <div
      className="flex items-center gap-2 rounded-xl border px-3 py-2 text-xs shadow-lg backdrop-blur-xl"
      style={{
        borderColor: `${entity.color}30`,
        backgroundColor: `${entity.color}08`,
      }}
    >
      <Handle type="target" position={Position.Left} className="!border-none !bg-transparent" />
      <span
        className="flex h-6 w-6 items-center justify-center rounded-lg text-[10px]"
        style={{ backgroundColor: `${entity.color}15`, color: entity.color }}
      >
        <Icon className="h-3.5 w-3.5" />
      </span>
      <span className="max-w-[140px] truncate font-medium text-[var(--text-primary)]">
        {entity.label}
      </span>
      <span
        className="rounded-full px-1.5 py-0.5 text-[8px] font-medium uppercase tracking-wider"
        style={{ backgroundColor: `${entity.color}15`, color: entity.color }}
      >
        {entity.type}
      </span>
      <Handle type="source" position={Position.Right} className="!border-none !bg-transparent" />
    </div>
  );
}

const nodeTypes = { entity: EntityNode };

interface KnowledgeGraphProps {
  answer: string;
  sources: SourceCitation[];
}

export default function KnowledgeGraph({ answer, sources }: KnowledgeGraphProps) {
  const { entities, relations } = useMemo(
    () => buildGraph(answer, sources.map((s) => ({ title: s.title, url: s.url }))),
    [answer, sources],
  );

  const initialNodes: Node[] = useMemo(
    () =>
      entities.map((entity, i) => ({
        id: entity.id,
        type: "entity",
        position: {
          x: 150 + Math.cos((i / entities.length) * Math.PI * 2) * 200,
          y: 100 + Math.sin((i / entities.length) * Math.PI * 2) * 200 + (i % 3) * 30,
        },
        data: { entity },
      })),
    [entities],
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      relations.map((r, i) => ({
        id: `e-${i}`,
        source: r.source,
        target: r.target,
        label: r.label,
        style: { stroke: "rgba(255,255,255,0.15)", strokeWidth: 1.5 },
        labelStyle: { fill: "rgba(255,255,255,0.3)", fontSize: 9 },
        markerEnd: { type: MarkerType.ArrowClosed, color: "rgba(255,255,255,0.2)" },
      })),
    [relations],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  if (entities.length === 0) return null;

  return (
    <section className="rounded-xl border border-white/[0.06] bg-white/[0.02]">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
        <div className="flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-violet-400" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            Knowledge graph
          </h2>
        </div>
        <span className="text-[9px] text-[var(--text-muted)]">
          {entities.length} entities · {relations.length} relations
        </span>
      </div>
      <div className="h-[350px]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.3}
          maxZoom={2}
          panOnDrag
          zoomOnScroll
          className="!bg-transparent"
        >
          <Background color="rgba(255,255,255,0.03)" gap={20} />
          <Controls
            className="!border-white/[0.06] !bg-[var(--surface)]"
            showInteractive={false}
          />
          <MiniMap
            className="!border-white/[0.06]"
            style={{ backgroundColor: "var(--surface)" }}
            nodeColor={() => "rgba(139, 92, 246, 0.3)"}
            maskColor="rgba(0,0,0,0.3)"
          />
        </ReactFlow>
      </div>
    </section>
  );
}
