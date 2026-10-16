import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  MarkerType,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  useStore,
  type Node,
  type OnNodeDrag,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Maximize2, Minus, Plus, RotateCcw } from "lucide-react";
import IconNode from "./IconNode";
import AnimatedEdge from "./AnimatedEdge";
import {
  defaultEdges,
  loadNodes,
  resetPositions,
  saveNodePositions,
  type WorkflowNodeData,
} from "../lib/workflowLayout";
import type { NodeExecution, NodeStatus } from "../types";

const nodeTypes = { iconNode: IconNode };
const edgeTypes = { animated: AnimatedEdge };

const NODE_SCALE_KEY = "claims-intel-node-scale-v1";

interface Props {
  nodeState: Record<string, NodeExecution>;
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
  resetKey: number;
  /** Edge ids with moving particles (current hop only). */
  activeEdgeIds?: string[];
  /** Edge ids already used on this run (static highlight). */
  traversedEdgeIds?: string[];
}

function loadNodeScale(): number {
  try {
    const raw = localStorage.getItem(NODE_SCALE_KEY);
    if (!raw) return 1;
    const n = Number(raw);
    return Number.isFinite(n) ? Math.min(2, Math.max(0.6, n)) : 1;
  } catch {
    return 1;
  }
}

function CanvasToolbar({
  nodeScale,
  onNodeScale,
  onResetLayout,
}: {
  nodeScale: number;
  onNodeScale: (v: number) => void;
  onResetLayout: () => void;
}) {
  const { zoomIn, zoomOut, fitView, setViewport, getViewport } = useReactFlow();
  const zoom = useStore((s) => s.transform[2]);

  const setZoomPercent = (pct: number) => {
    const next = Math.min(2.5, Math.max(0.25, pct / 100));
    const vp = getViewport();
    setViewport({ ...vp, zoom: next }, { duration: 120 });
  };

  return (
    <Panel position="top-right" className="!m-3">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-navy-900/95 px-3 py-2 shadow-lg backdrop-blur">
        <span className="text-[10px] uppercase tracking-wide text-slate-500">Zoom</span>
        <button
          type="button"
          onClick={() => zoomOut({ duration: 120 })}
          className="rounded-md border border-white/10 p-1.5 text-slate-300 hover:bg-white/5"
          title="Zoom out"
        >
          <Minus className="h-3.5 w-3.5" />
        </button>
        <input
          type="range"
          min={25}
          max={250}
          step={5}
          value={Math.round(zoom * 100)}
          onChange={(e) => setZoomPercent(Number(e.target.value))}
          className="h-1.5 w-24 cursor-pointer accent-accent-cyan"
          title="Canvas zoom"
        />
        <button
          type="button"
          onClick={() => zoomIn({ duration: 120 })}
          className="rounded-md border border-white/10 p-1.5 text-slate-300 hover:bg-white/5"
          title="Zoom in"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
        <span className="min-w-[3rem] text-center font-mono text-[11px] text-slate-400">
          {Math.round(zoom * 100)}%
        </span>
        <button
          type="button"
          onClick={() => fitView({ padding: 0.15, duration: 200 })}
          className="rounded-md border border-white/10 p-1.5 text-slate-300 hover:bg-white/5"
          title="Fit view"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>

        <div className="mx-1 h-5 w-px bg-white/10" />

        <span className="text-[10px] uppercase tracking-wide text-slate-500">Icons</span>
        <button
          type="button"
          onClick={() => onNodeScale(Math.max(0.6, Number((nodeScale - 0.1).toFixed(1))))}
          className="rounded-md border border-white/10 p-1.5 text-slate-300 hover:bg-white/5"
          title="Smaller icons"
        >
          <Minus className="h-3.5 w-3.5" />
        </button>
        <input
          type="range"
          min={60}
          max={200}
          step={10}
          value={Math.round(nodeScale * 100)}
          onChange={(e) => onNodeScale(Number(e.target.value) / 100)}
          className="h-1.5 w-24 cursor-pointer accent-accent-violet"
          title="Icon size"
        />
        <button
          type="button"
          onClick={() => onNodeScale(Math.min(2, Number((nodeScale + 0.1).toFixed(1))))}
          className="rounded-md border border-white/10 p-1.5 text-slate-300 hover:bg-white/5"
          title="Larger icons"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
        <span className="min-w-[3rem] text-center font-mono text-[11px] text-slate-400">
          {Math.round(nodeScale * 100)}%
        </span>

        <button
          type="button"
          onClick={onResetLayout}
          className="rounded-md border border-white/10 p-1.5 text-slate-300 hover:bg-white/5"
          title="Reset layout"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      </div>
    </Panel>
  );
}

function CanvasInner({
  nodeState,
  selectedNodeId,
  onSelectNode,
  resetKey,
  activeEdgeIds = [],
  traversedEdgeIds = [],
}: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState(loadNodes());
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    defaultEdges.map((e) => ({
      ...e,
      markerEnd: { type: MarkerType.ArrowClosed, color: "#94a3b8", width: 18, height: 18 },
    }))
  );
  const [nodeScale, setNodeScale] = useState(loadNodeScale);
  const { fitView } = useReactFlow();
  const activeSet = useMemo(() => new Set(activeEdgeIds), [activeEdgeIds]);
  const traversedSet = useMemo(() => new Set(traversedEdgeIds), [traversedEdgeIds]);

  const applyNodeScale = useCallback((value: number) => {
    const next = Math.min(2, Math.max(0.6, value));
    setNodeScale(next);
    localStorage.setItem(NODE_SCALE_KEY, String(next));
  }, []);

  useEffect(() => {
    if (resetKey > 0) {
      setNodes(resetPositions());
      applyNodeScale(1);
      setTimeout(() => fitView({ padding: 0.15 }), 50);
    }
  }, [resetKey, setNodes, fitView, applyNodeScale]);

  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => {
        const exec = nodeState[n.id];
        const status: NodeStatus = exec?.status || "idle";
        return {
          ...n,
          selected: n.id === selectedNodeId,
          data: { ...(n.data as WorkflowNodeData), status, scale: nodeScale },
        };
      })
    );

    setEdges((eds) =>
      eds.map((e) => {
        const active = activeSet.has(e.id);
        const traversed = traversedSet.has(e.id);
        return {
          ...e,
          data: { ...(e.data || {}), active, traversed },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: active ? "#22d3ee" : traversed ? "#38bdf8" : "#94a3b8",
            width: active ? 20 : 18,
            height: active ? 20 : 18,
          },
        };
      })
    );
  }, [nodeState, selectedNodeId, nodeScale, activeSet, traversedSet, setNodes, setEdges]);

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => onSelectNode(node.id),
    [onSelectNode]
  );

  const onNodeDragStop: OnNodeDrag = useCallback((_event, _node, allNodes) => {
    saveNodePositions(allNodes);
  }, []);

  const miniColors = useMemo(
    () => (n: Node) => {
      const s = (n.data as WorkflowNodeData).status;
      if (s === "running") return "#3b82f6";
      if (s === "completed") return "#22c55e";
      if (s === "failed") return "#ef4444";
      return "#334155";
    },
    []
  );

  return (
    <div className="workflow-grid h-full w-full overflow-hidden rounded-xl border border-white/10">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onNodeDragStop={onNodeDragStop}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        minZoom={0.25}
        maxZoom={2.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={22}
          size={1}
          color="rgba(148,163,184,0.25)"
        />
        <Controls showInteractive={false} className="!border-white/10 !bg-navy-800 !shadow-lg" />
        <MiniMap
          nodeColor={miniColors}
          maskColor="rgba(7,11,22,0.75)"
          className="!border-white/10 !bg-navy-900"
        />
        <CanvasToolbar
          nodeScale={nodeScale}
          onNodeScale={applyNodeScale}
          onResetLayout={() => {
            setNodes(resetPositions());
            applyNodeScale(1);
            setTimeout(() => fitView({ padding: 0.15 }), 50);
          }}
        />
      </ReactFlow>
    </div>
  );
}

export default function WorkflowCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <CanvasInner {...props} />
    </ReactFlowProvider>
  );
}
