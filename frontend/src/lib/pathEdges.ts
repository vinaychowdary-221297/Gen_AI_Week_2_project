/**
 * Maps a workflow node to the canvas edge(s) that should light up
 * when that node starts — only those path segments animate.
 */
export const INCOMING_EDGES: Record<string, string[]> = {
  start_trigger: [],
  claim_intake: ["e1"],
  langgraph_agent: ["e2", "e12"], // e12 = RRF feedback loop (only if RRF already ran)
  nebius_llm: ["e3"],
  claim_lookup: ["e4"],
  claim_database: ["e5"],
  portfolio_lookup: ["e4b"],
  hybrid_retrieval: ["e6"],
  bm25_search: ["e7"],
  embeddings: ["e8"],
  pinecone_search: ["e9"],
  rrf_fusion: ["e10", "e11"],
  coverage_check: ["e13"],
  estimate_analysis: ["e14"],
  missing_documents: ["e15"],
  similar_claims: ["e16"],
  report_generator: ["e17"],
  human_review: ["e18"],
};

/** Prefer these sources when a node has multiple possible inbound edges. */
const EDGE_SOURCE: Record<string, string> = {
  e1: "start_trigger",
  e2: "claim_intake",
  e3: "langgraph_agent",
  e4: "langgraph_agent",
  e5: "claim_lookup",
  e4b: "langgraph_agent",
  e6: "langgraph_agent",
  e7: "hybrid_retrieval",
  e8: "hybrid_retrieval",
  e9: "embeddings",
  e10: "bm25_search",
  e11: "pinecone_search",
  e12: "rrf_fusion",
  e13: "langgraph_agent",
  e14: "langgraph_agent",
  e15: "langgraph_agent",
  e16: "langgraph_agent",
  e17: "langgraph_agent",
  e18: "report_generator",
};

export function edgesForNodeStart(
  nodeId: string,
  visited: Set<string>
): string[] {
  const candidates = INCOMING_EDGES[nodeId] || [];
  if (candidates.length === 0) return [];

  // Only activate edges whose source has already been visited/started
  const ready = candidates.filter((eid) => {
    const src = EDGE_SOURCE[eid];
    if (!src) return false;
    // Feedback loop: only if RRF was visited
    if (eid === "e12") return visited.has("rrf_fusion");
    // First entry into agent uses intake edge, not feedback
    if (nodeId === "langgraph_agent" && eid === "e2") {
      return visited.has("claim_intake") || !visited.has("langgraph_agent");
    }
    if (nodeId === "langgraph_agent" && eid === "e12") {
      return visited.has("rrf_fusion");
    }
    // RRF: only light branch edges whose source already ran
    if (nodeId === "rrf_fusion") {
      return visited.has(src);
    }
    return visited.has(src) || src === "langgraph_agent";
  });

  if (nodeId === "langgraph_agent") {
    // Prefer feedback if RRF done, else intake
    if (visited.has("rrf_fusion") && ready.includes("e12")) return ["e12"];
    if (ready.includes("e2")) return ["e2"];
  }

  return ready.length ? ready : candidates.filter((eid) => {
    // Fallback for first hops from agent tools
    const src = EDGE_SOURCE[eid];
    return src === "langgraph_agent" || visited.has(src || "");
  });
}
