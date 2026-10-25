import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, eventsUrl } from "../lib/api";
import { edgesForNodeStart } from "../lib/pathEdges";
import type { InvestigationReport, NodeExecution, NodeStatus, WorkflowEvent } from "../types";
import type { ProcessStage } from "../components/ProcessPipeline";

function mapStatus(eventType: string, status: string): NodeStatus | null {
  if (eventType === "node_started" || eventType === "tool_called" || eventType === "retrieval_started") {
    return "running";
  }
  if (
    eventType === "node_completed" ||
    eventType === "tool_result" ||
    eventType === "retrieval_completed" ||
    eventType === "report_generated" ||
    eventType === "handoff_requested" ||
    eventType === "stage_changed"
  ) {
    return "completed";
  }
  if (eventType === "node_failed" || eventType === "workflow_failed") {
    return "failed";
  }
  if (status === "running") return "running";
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  return null;
}

function stageFromEvent(ev: WorkflowEvent): ProcessStage | null {
  if (ev.event_type === "stage_changed" && ev.input_summary && typeof ev.input_summary === "object") {
    const s = (ev.input_summary as { stage?: string }).stage;
    if (
      s === "filing" ||
      s === "classification" ||
      s === "investigation" ||
      s === "report" ||
      s === "human_review"
    ) {
      return s;
    }
  }
  if (ev.event_type === "handoff_requested") return "human_review";
  if (ev.node_id?.startsWith("stage_")) {
    const s = ev.node_id.replace("stage_", "");
    if (
      s === "filing" ||
      s === "classification" ||
      s === "investigation" ||
      s === "report" ||
      s === "human_review"
    ) {
      return s;
    }
  }
  return null;
}

export type InvestigationApi = {
  running: boolean;
  runId: string | null;
  logs: WorkflowEvent[];
  nodeState: Record<string, NodeExecution>;
  report: InvestigationReport | null;
  error: string | null;
  currentStage: ProcessStage;
  handoff: boolean;
  activeEdgeIds: string[];
  traversedEdgeIds: string[];
  claimId: string | null;
  question: string | null;
  start: (claimId: string | null | undefined, question: string) => Promise<void>;
  reset: () => void;
};

const InvestigationContext = createContext<InvestigationApi | null>(null);

function useInvestigationState(): InvestigationApi {
  const [running, setRunning] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [logs, setLogs] = useState<WorkflowEvent[]>([]);
  const [nodeState, setNodeState] = useState<Record<string, NodeExecution>>({});
  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentStage, setCurrentStage] = useState<ProcessStage>(null);
  const [handoff, setHandoff] = useState(false);
  const [activeEdgeIds, setActiveEdgeIds] = useState<string[]>([]);
  const [traversedEdgeIds, setTraversedEdgeIds] = useState<string[]>([]);
  const [claimId, setClaimId] = useState<string | null>(null);
  const [question, setQuestion] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const lastEventId = useRef<string | undefined>(undefined);
  const visitedRef = useRef<Set<string>>(new Set());
  const activeEdgesRef = useRef<string[]>([]);

  const reset = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
    setLogs([]);
    setNodeState({});
    setReport(null);
    setError(null);
    setRunId(null);
    setCurrentStage(null);
    setHandoff(false);
    setActiveEdgeIds([]);
    setTraversedEdgeIds([]);
    setClaimId(null);
    setQuestion(null);
    lastEventId.current = undefined;
    visitedRef.current = new Set();
    activeEdgesRef.current = [];
  }, []);

  const applyEvent = useCallback((ev: WorkflowEvent) => {
    if (ev.event_type === "heartbeat") return;
    lastEventId.current = ev.event_id;
    setLogs((prev) => [...prev, ev]);

    if (ev.node_id) {
      const nextStatus = mapStatus(ev.event_type, ev.status);

      if (
        (ev.event_type === "node_started" ||
          ev.event_type === "tool_called" ||
          ev.event_type === "retrieval_started") &&
        ev.node_id
      ) {
        const incoming = edgesForNodeStart(ev.node_id, visitedRef.current);
        visitedRef.current.add(ev.node_id);

        if (activeEdgesRef.current.length) {
          const finished = [...activeEdgesRef.current];
          setTraversedEdgeIds((prev) => Array.from(new Set([...prev, ...finished])));
        }
        activeEdgesRef.current = incoming;
        setActiveEdgeIds(incoming);
      }

      if (
        (ev.event_type === "node_completed" ||
          ev.event_type === "tool_result" ||
          ev.event_type === "retrieval_completed" ||
          ev.event_type === "report_generated") &&
        ev.node_id
      ) {
        visitedRef.current.add(ev.node_id);
        const inbound = edgesForNodeStart(ev.node_id, visitedRef.current);
        setTraversedEdgeIds((prev) => Array.from(new Set([...prev, ...inbound])));
      }

      setNodeState((prev) => {
        const existing = prev[ev.node_id!] || { status: "idle" as NodeStatus, history: [] };
        const updated: NodeExecution = {
          ...existing,
          history: [...existing.history, ev],
        };
        if (nextStatus) updated.status = nextStatus;
        if (ev.input_summary !== undefined && ev.input_summary !== null) {
          updated.input = ev.input_summary;
        }
        if (ev.output_summary !== undefined && ev.output_summary !== null) {
          updated.output = ev.output_summary;
        }
        if (ev.duration_ms != null) updated.duration_ms = ev.duration_ms;
        if (ev.error) updated.error = ev.error;
        return { ...prev, [ev.node_id!]: updated };
      });
    }

    const stage = stageFromEvent(ev);
    if (stage) setCurrentStage(stage);

    if (ev.event_type === "report_generated" && ev.output_summary) {
      setReport(ev.output_summary as InvestigationReport);
      setCurrentStage((prev) => prev || "report");
    }
    if (ev.event_type === "handoff_requested") {
      setHandoff(true);
      setCurrentStage("human_review");
      activeEdgesRef.current = [];
      setActiveEdgeIds([]);
      setRunning(false);
      if (ev.run_id) {
        api
          .run(ev.run_id)
          .then((r) => {
            if (r.report) setReport(r.report);
          })
          .catch(() => undefined);
      }
    }
    if (ev.event_type === "workflow_completed") {
      activeEdgesRef.current = [];
      setActiveEdgeIds([]);
      setRunning(false);
      if (ev.status === "awaiting_human") {
        setHandoff(true);
        setCurrentStage("human_review");
      } else {
        setCurrentStage("human_review");
      }
      if (ev.run_id) {
        api
          .run(ev.run_id)
          .then((r) => {
            if (r.report) setReport(r.report);
          })
          .catch(() => undefined);
      }
    }
    if (ev.event_type === "workflow_failed") {
      activeEdgesRef.current = [];
      setActiveEdgeIds([]);
      setRunning(false);
      setError(ev.error || "Investigation failed");
    }
  }, []);

  const subscribe = useCallback(
    (id: string) => {
      sourceRef.current?.close();
      const url = eventsUrl(id, lastEventId.current);
      const es = new EventSource(url);
      sourceRef.current = es;

      const handler = (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as WorkflowEvent;
          applyEvent(data);
        } catch {
          /* ignore malformed */
        }
      };

      [
        "workflow_started",
        "node_started",
        "node_completed",
        "node_failed",
        "tool_called",
        "tool_result",
        "retrieval_started",
        "retrieval_completed",
        "report_generated",
        "handoff_requested",
        "stage_changed",
        "tool_retry",
        "workflow_completed",
        "workflow_failed",
        "heartbeat",
        "message",
      ].forEach((name) => es.addEventListener(name, handler as EventListener));

      es.onerror = () => {
        /* browser retry */
      };
    },
    [applyEvent]
  );

  const start = useCallback(
    async (nextClaimId: string | null | undefined, nextQuestion: string) => {
      reset();
      setClaimId(nextClaimId || null);
      setQuestion(nextQuestion);
      setRunning(true);
      try {
        const res = await api.investigate(nextClaimId, nextQuestion);
        setRunId(res.run_id);
        subscribe(res.run_id);
      } catch (err) {
        setRunning(false);
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [reset, subscribe]
  );

  return useMemo(
    () => ({
      running,
      runId,
      logs,
      nodeState,
      report,
      error,
      currentStage,
      handoff,
      activeEdgeIds,
      traversedEdgeIds,
      claimId,
      question,
      start,
      reset,
    }),
    [
      running,
      runId,
      logs,
      nodeState,
      report,
      error,
      currentStage,
      handoff,
      activeEdgeIds,
      traversedEdgeIds,
      claimId,
      question,
      start,
      reset,
    ]
  );
}

export function InvestigationProvider({ children }: { children: ReactNode }) {
  const value = useInvestigationState();
  return createElement(InvestigationContext.Provider, { value }, children);
}

export function useInvestigation(): InvestigationApi {
  const ctx = useContext(InvestigationContext);
  if (!ctx) {
    throw new Error("useInvestigation must be used within InvestigationProvider");
  }
  return ctx;
}
