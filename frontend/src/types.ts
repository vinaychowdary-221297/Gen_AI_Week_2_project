export type NodeStatus = "idle" | "running" | "completed" | "failed" | "skipped";

export interface ClaimSummary {
  claim_id: string;
  policy_id: string;
  policy_number: string;
  insured_name: string;
  accident_date: string;
  accident_description: string;
  claim_status: string;
  vehicle: {
    year: number;
    make: string;
    model: string;
    trim?: string;
    vin?: string;
    color?: string;
  };
  location: string;
  submitted_documents: string[];
  estimate_total: number;
  scenario_tag?: string;
  coverages: string[];
  collision_deductible: number;
}

export interface ClaimListItem {
  claim_id: string;
  policy_id: string;
  accident_date: string;
  accident_description: string;
  claim_status: string;
  scenario_tag?: string;
  estimate_total: number;
  vehicle: ClaimSummary["vehicle"];
}

export interface HealthStatus {
  status: string;
  backend: { ok: boolean };
  nebius: { ok: boolean; error?: string; chat_model?: string; embed_model?: string };
  pinecone: { ok: boolean; error?: string; exists?: boolean; ready?: boolean };
  bm25: { ok: boolean; chunks: number };
  models: { chat: string; embed: string };
}

export interface WorkflowEvent {
  run_id: string;
  event_id: string;
  timestamp: string;
  event_type: string;
  status: string;
  node_id?: string | null;
  duration_ms?: number | null;
  input_summary?: unknown;
  output_summary?: unknown;
  error?: string | null;
  tool_name?: string;
}

export interface NodeExecution {
  status: NodeStatus;
  input?: unknown;
  output?: unknown;
  error?: string;
  duration_ms?: number;
  history: WorkflowEvent[];
}

export interface InvestigationReport {
  claim_id: string;
  investigation_status: string;
  claim_summary: string;
  policy_facts: Record<string, unknown>;
  retrieved_evidence: Array<{
    document_name: string;
    section?: string;
    page_number?: number | null;
    excerpt: string;
    chunk_id?: string;
    score?: number;
  }>;
  coverage_considerations: string[];
  estimate_analysis: Record<string, unknown>;
  potential_discrepancies: string[];
  missing_documents: string[];
  illustrative_financials: Record<string, unknown>;
  recommended_next_steps: string[];
  unresolved_questions: string[];
  human_review_required: boolean;
  disclaimer?: string;
}
