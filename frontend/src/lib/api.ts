import type { ClaimListItem, ClaimSummary, HealthStatus, InvestigationReport } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthStatus>("/api/health"),
  claims: () => request<ClaimListItem[]>("/api/claims"),
  claim: (id: string) => request<ClaimSummary>(`/api/claims/${id}`),
  exampleQuestions: (claimId?: string) =>
    request<string[]>(
      claimId ? `/api/example-questions?claim_id=${encodeURIComponent(claimId)}` : "/api/example-questions"
    ),
  evaluationQuestions: () => request<Array<Record<string, unknown>>>("/api/evaluation/questions"),
  investigate: (claimId: string | null | undefined, question: string) =>
    request<{ run_id: string; claim_id: string; status: string; stream_url: string }>(
      "/api/investigate",
      {
        method: "POST",
        body: JSON.stringify({
          claim_id: claimId && claimId.trim() ? claimId.trim() : null,
          question,
        }),
      }
    ),
  run: (runId: string) =>
    request<{ run_id: string; status: string; report?: InvestigationReport; error?: string }>(
      `/api/runs/${runId}`
    ),
};

export function eventsUrl(runId: string, lastEventId?: string) {
  const base = `${API_BASE}/api/runs/${runId}/events`;
  if (!lastEventId) return base;
  return `${base}?last_event_id=${encodeURIComponent(lastEventId)}`;
}
