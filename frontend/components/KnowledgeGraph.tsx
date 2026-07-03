"use client";

import { useMemo, useEffect, useState, useCallback } from "react";
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
import { BrainCircuit, Globe2, FileText, Lightbulb, Building2, BookOpen, Search, Filter } from "lucide-react";
import type { SourceCitation } from "@/lib/types";
import { buildGraph, ENTITY_TYPE_CONFIG, type GraphEntity } from "@/lib/knowledge-graph";
import { cn } from "@/lib/utils";

const typeIcons: Record<string, React.ElementType> = {
  concept: Lightbulb,
  technology: Globe2,
  company: Building2,
  paper: FileText,
  topic: BookOpen,
};

const typeColors: Record<string, string> = Object.fromEntries(
  ENTITY_TYPE_CONFIG.map((c) => [c.type, c.color]),
);
typeColors.person = "#f472b6";

const ENTITY_TYPES = ENTITY_TYPE_CONFIG.map((c) => c.type);

function EntityNode({ data }: NodeProps) {
  const entity = data.entity as GraphEntity;
  const Icon = typeIcons[entity.type] || BrainCircuit;
  const color = typeColors[entity.type] || "#8b5cf6";

  return (
    <div
      className="flex items-center gap-2 rounded-xl border px-3 py-2 text-xs shadow-lg backdrop-blur-xl"
      style={{
        borderColor: `${color}30`,
        backgroundColor: `${color}08`,
      }}
    >
      <Handle type="target" position={Position.Left} className="!border-none !bg-transparent" />
      <span
        className="flex h-6 w-6 items-center justify-center rounded-lg text-[10px]"
        style={{ backgroundColor: `${color}15`, color }}
      >
        <Icon className="h-3.5 w-3.5" />
      </span>
      <span className="max-w-[140px] truncate font-medium text-[var(--text-primary)]">
        {entity.label}
      </span>
      <span
        className="rounded-full px-1.5 py-0.5 text-[8px] font-medium uppercase tracking-wider"
        style={{ backgroundColor: `${color}15`, color }}
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
  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  const { entities: allEntities, relations: allRelations } = useMemo(
    () => buildGraph(answer, sources.map((s) => ({ title: s.title, url: s.url }))),
    [answer, sources],
  );

  const filteredEntities = useMemo(() => {
    let ents = allEntities;
    if (filter !== "all") {
      ents = ents.filter((e) => e.type === filter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      ents = ents.filter((e) => e.label.toLowerCase().includes(q));
    }
    return ents;
  }, [allEntities, filter, search]);

  const filteredEntityIds = useMemo(
    () => new Set(filteredEntities.map((e) => e.id)),
    [filteredEntities],
  );

  const filteredRelations = useMemo(
    () => allRelations.filter(
      (r) => filteredEntityIds.has(r.source) && filteredEntityIds.has(r.target),
    ),
    [allRelations, filteredEntityIds],
  );

  const initialNodes: Node[] = useMemo(
    () =>
      filteredEntities.map((entity, i) => ({
        id: entity.id,
        type: "entity",
        position: {
          x: 150 + Math.cos((i / Math.max(filteredEntities.length, 1)) * Math.PI * 2) * 200,
          y: 100 + Math.sin((i / Math.max(filteredEntities.length, 1)) * Math.PI * 2) * 200 + (i % 3) * 30,
        },
        data: { entity },
      })),
    [filteredEntities],
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      filteredRelations.map((r, i) => ({
        id: `e-${i}`,
        source: r.source,
        target: r.target,
        label: r.label,
        style: { stroke: "rgba(255,255,255,0.15)", strokeWidth: 1.5 },
        labelStyle: { fill: "rgba(255,255,255,0.3)", fontSize: 9 },
        markerEnd: { type: MarkerType.ArrowClosed, color: "rgba(255,255,255,0.2)" },
      })),
    [filteredRelations],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, _setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  if (allEntities.length === 0) return null;

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
          {allEntities.length} entities · {allRelations.length} relations
        </span>
      </div>

      <div className="flex items-center gap-2 border-b border-white/[0.06] px-3 py-2">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="text"
            placeholder="Search entities..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] py-1.5 pl-7 pr-2 text-[11px] text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none transition-colors focus:border-white/[0.12]"
          />
        </div>
        <div className="flex gap-1">
          {["all", ...ENTITY_TYPES].map((t) => (
            <button
              key={t}
              onClick={() => setFilter(t)}
              className={cn(
                "rounded-md px-2 py-1 text-[9px] font-medium capitalize transition-colors",
                filter === t
                  ? "bg-white/[0.1] text-[var(--text-primary)]"
                  : "text-[var(--text-muted)] hover:bg-white/[0.05]",
              )}
            >
              {t}
            </button>
          ))}
        </div>
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
