import type { Edge, Node } from "@xyflow/react";

const STORAGE_KEY = "claims-intel-workflow-positions-v4";

export type WorkflowNodeData = {
  label: string;
  subtitle?: string;
  icon: string;
  accent: string;
  status: "idle" | "running" | "completed" | "failed" | "skipped";
  scale?: number;
};

const defaultNodes: Node<WorkflowNodeData>[] = [
  {
    id: "start_trigger",
    position: { x: 20, y: 300 },
    data: { label: "Human Input", icon: "user", accent: "#38bdf8", status: "idle" },
    type: "iconNode",
  },
  {
    id: "claim_intake",
    position: { x: 200, y: 300 },
    data: { label: "Claim Intake", icon: "file-text", accent: "#22d3ee", status: "idle" },
    type: "iconNode",
  },
  {
    id: "langgraph_agent",
    position: { x: 400, y: 300 },
    data: { label: "LangGraph Agent", icon: "brain", accent: "#8b5cf6", status: "idle" },
    type: "iconNode",
  },
  {
    id: "nebius_llm",
    position: { x: 400, y: 140 },
    data: { label: "Nebius LLM", icon: "sparkles", accent: "#a78bfa", status: "idle" },
    type: "iconNode",
  },
  {
    id: "claim_lookup",
    position: { x: 660, y: 40 },
    data: { label: "Claim Lookup", icon: "search", accent: "#22d3ee", status: "idle" },
    type: "iconNode",
  },
  {
    id: "claim_database",
    position: { x: 860, y: 40 },
    data: { label: "Claim Database", icon: "database", accent: "#38bdf8", status: "idle" },
    type: "iconNode",
  },
  {
    id: "portfolio_lookup",
    position: { x: 860, y: -80 },
    data: { label: "Portfolio Lookup", icon: "database", accent: "#67e8f9", status: "idle" },
    type: "iconNode",
  },
  {
    id: "hybrid_retrieval",
    position: { x: 660, y: 180 },
    data: { label: "Hybrid Retrieval", icon: "git-merge", accent: "#60a5fa", status: "idle" },
    type: "iconNode",
  },
  {
    id: "bm25_search",
    position: { x: 900, y: 120 },
    data: { label: "BM25 Search", icon: "search", accent: "#f59e0b", status: "idle" },
    type: "iconNode",
  },
  {
    id: "embeddings",
    position: { x: 900, y: 230 },
    data: { label: "Embeddings", icon: "vector", accent: "#22d3ee", status: "idle" },
    type: "iconNode",
  },
  {
    id: "pinecone_search",
    position: { x: 1100, y: 230 },
    data: { label: "Pinecone Search", icon: "pinecone", accent: "#34d399", status: "idle" },
    type: "iconNode",
  },
  {
    id: "rrf_fusion",
    position: { x: 1300, y: 175 },
    data: { label: "RRF Fusion", icon: "merge", accent: "#818cf8", status: "idle" },
    type: "iconNode",
  },
  {
    id: "coverage_check",
    position: { x: 660, y: 340 },
    data: { label: "Coverage Check", icon: "shield-check", accent: "#22c55e", status: "idle" },
    type: "iconNode",
  },
  {
    id: "estimate_analysis",
    position: { x: 660, y: 460 },
    data: { label: "Estimate Analysis", icon: "calculator", accent: "#f59e0b", status: "idle" },
    type: "iconNode",
  },
  {
    id: "missing_documents",
    position: { x: 660, y: 580 },
    data: { label: "Missing Documents", icon: "folder-search", accent: "#fb7185", status: "idle" },
    type: "iconNode",
  },
  {
    id: "similar_claims",
    position: { x: 660, y: 700 },
    data: { label: "Similar Claims", icon: "files", accent: "#38bdf8", status: "idle" },
    type: "iconNode",
  },
  {
    id: "report_generator",
    position: { x: 960, y: 420 },
    data: { label: "Output Report Generator", icon: "file-check", accent: "#22c55e", status: "idle" },
    type: "iconNode",
  },
  {
    id: "human_review",
    position: { x: 1220, y: 420 },
    data: { label: "Human Review", icon: "user-check", accent: "#f59e0b", status: "idle" },
    type: "iconNode",
  },
];

export const defaultEdges: Edge[] = [
  { id: "e1", source: "start_trigger", target: "claim_intake", type: "animated", data: { active: false } },
  { id: "e2", source: "claim_intake", target: "langgraph_agent", type: "animated", data: { active: false } },
  { id: "e3", source: "langgraph_agent", target: "nebius_llm", type: "animated", data: { active: false } },
  { id: "e4", source: "langgraph_agent", target: "claim_lookup", type: "animated", data: { active: false } },
  { id: "e5", source: "claim_lookup", target: "claim_database", type: "animated", data: { active: false } },
  { id: "e4b", source: "langgraph_agent", target: "portfolio_lookup", type: "animated", data: { active: false } },
  { id: "e6", source: "langgraph_agent", target: "hybrid_retrieval", type: "animated", data: { active: false } },
  { id: "e7", source: "hybrid_retrieval", target: "bm25_search", type: "animated", data: { active: false } },
  { id: "e8", source: "hybrid_retrieval", target: "embeddings", type: "animated", data: { active: false } },
  { id: "e9", source: "embeddings", target: "pinecone_search", type: "animated", data: { active: false } },
  { id: "e10", source: "bm25_search", target: "rrf_fusion", type: "animated", data: { active: false } },
  { id: "e11", source: "pinecone_search", target: "rrf_fusion", type: "animated", data: { active: false } },
  { id: "e12", source: "rrf_fusion", target: "langgraph_agent", type: "animated", data: { active: false, feedback: true } },
  { id: "e13", source: "langgraph_agent", target: "coverage_check", type: "animated", data: { active: false } },
  { id: "e14", source: "langgraph_agent", target: "estimate_analysis", type: "animated", data: { active: false } },
  { id: "e15", source: "langgraph_agent", target: "missing_documents", type: "animated", data: { active: false } },
  { id: "e16", source: "langgraph_agent", target: "similar_claims", type: "animated", data: { active: false } },
  { id: "e17", source: "langgraph_agent", target: "report_generator", type: "animated", data: { active: false } },
  { id: "e18", source: "report_generator", target: "human_review", type: "animated", data: { active: false } },
];

export function loadNodes(): Node<WorkflowNodeData>[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultNodes.map((n) => ({ ...n, data: { ...n.data } }));
    const positions = JSON.parse(raw) as Record<string, { x: number; y: number }>;
    return defaultNodes.map((n) => ({
      ...n,
      position: positions[n.id] || n.position,
      data: { ...n.data },
    }));
  } catch {
    return defaultNodes.map((n) => ({ ...n, data: { ...n.data } }));
  }
}

export function saveNodePositions(nodes: Node[]) {
  const positions: Record<string, { x: number; y: number }> = {};
  nodes.forEach((n) => {
    positions[n.id] = n.position;
  });
  localStorage.setItem(STORAGE_KEY, JSON.stringify(positions));
}

export function resetPositions() {
  localStorage.removeItem(STORAGE_KEY);
  return defaultNodes.map((n) => ({ ...n, data: { ...n.data } }));
}
