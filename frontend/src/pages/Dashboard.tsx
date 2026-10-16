import { useEffect, useRef, useState } from "react";
import ClaimSidebar from "../components/ClaimSidebar";
import WorkflowCanvas from "../components/WorkflowCanvas";
import NodeInspector from "../components/NodeInspector";
import BottomPanel from "../components/BottomPanel";
import { api } from "../lib/api";
import { useInvestigation } from "../hooks/useInvestigation";
import type { ClaimListItem, ClaimSummary } from "../types";

const DEFAULT_Q =
  "Investigate this claim: validate policy dates, check coverage facts, analyze the repair estimate, identify missing documents, retrieve relevant policy clauses, and produce an investigation report.";

const PORTFOLIO_Q = "How many policies are active?";

const BOTTOM_H_KEY = "claims-intel-bottom-height-v1";

function loadBottomHeight(): number {
  try {
    const n = Number(localStorage.getItem(BOTTOM_H_KEY));
    return Number.isFinite(n) ? Math.min(480, Math.max(140, n)) : 220;
  } catch {
    return 220;
  }
}

export default function Dashboard() {
  const [claims, setClaims] = useState<ClaimListItem[]>([]);
  const [claimId, setClaimId] = useState("CLM-1001");
  const [claim, setClaim] = useState<ClaimSummary | null>(null);
  const [question, setQuestion] = useState(DEFAULT_Q);
  const [examples, setExamples] = useState<string[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [bottomH, setBottomH] = useState(loadBottomHeight);
  const dragRef = useRef<{ startY: number; startH: number } | null>(null);
  const inv = useInvestigation();

  useEffect(() => {
    api
      .claims()
      .then((list) => {
        setClaims(list);
        if (list.length && !list.find((c) => c.claim_id === claimId)) {
          setClaimId(list[0].claim_id);
        }
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!claimId) {
      setClaim(null);
      setQuestion((q) => (q === DEFAULT_Q || !q.trim() ? PORTFOLIO_Q : q));
      api.exampleQuestions().then(setExamples).catch(() => undefined);
      return;
    }
    api.claim(claimId).then(setClaim).catch(console.error);
    api.exampleQuestions(claimId).then(setExamples).catch(() => undefined);
  }, [claimId]);

  useEffect(() => {
    localStorage.setItem(BOTTOM_H_KEY, String(bottomH));
  }, [bottomH]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragRef.current) return;
      const delta = dragRef.current.startY - e.clientY;
      const next = Math.min(480, Math.max(140, dragRef.current.startH + delta));
      setBottomH(next);
    };
    const onUp = () => {
      dragRef.current = null;
      document.body.style.cursor = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  return (
    <div className="mx-auto grid h-[calc(100vh-72px)] max-w-[1800px] grid-cols-12 gap-3 p-3">
      <div className="col-span-3 min-h-0">
        <ClaimSidebar
          claimIds={claims.map((c) => c.claim_id)}
          selectedClaimId={claimId}
          onSelectClaim={setClaimId}
          claim={claim}
          question={question}
          onQuestionChange={setQuestion}
          examples={examples}
          onRun={() => inv.start(claimId, question)}
          running={inv.running}
        />
      </div>

      <div className="col-span-9 flex min-h-0 flex-col gap-0">
        <div className="flex min-h-0 flex-1 gap-3" style={{ minHeight: 200 }}>
          <div className="flex min-h-0 flex-1 flex-col gap-2">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-display text-sm font-semibold text-white">
                  Live Workflow Canvas
                </h2>
                <p className="text-[11px] text-slate-500">
                  Zoom / icon size controls are on the canvas · drag the bar below to resize
                  {inv.runId ? ` · run ${inv.runId.slice(0, 8)}…` : ""}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setBottomH((h) => Math.max(140, h - 40))}
                  className="rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-400 hover:bg-white/5"
                  title="Taller canvas"
                >
                  Canvas +
                </button>
                <button
                  onClick={() => setBottomH((h) => Math.min(480, h + 40))}
                  className="rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-400 hover:bg-white/5"
                  title="Shorter canvas"
                >
                  Canvas −
                </button>
                <button
                  onClick={() => setResetKey((k) => k + 1)}
                  className="rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-400 hover:bg-white/5"
                >
                  Reset layout
                </button>
              </div>
            </div>
            {inv.error && (
              <div className="rounded-md border border-accent-red/40 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
                {inv.error}
              </div>
            )}
            <div className="min-h-0 flex-1">
              <WorkflowCanvas
                nodeState={inv.nodeState}
                selectedNodeId={selectedNodeId}
                onSelectNode={setSelectedNodeId}
                resetKey={resetKey}
                activeEdgeIds={inv.activeEdgeIds}
                traversedEdgeIds={inv.traversedEdgeIds}
              />
            </div>
          </div>

          <div className="w-[300px] shrink-0 min-h-0">
            <NodeInspector
              nodeId={selectedNodeId}
              execution={selectedNodeId ? inv.nodeState[selectedNodeId] : undefined}
            />
          </div>
        </div>

        <div
          className="group flex h-3 cursor-row-resize items-center justify-center"
          onMouseDown={(e) => {
            dragRef.current = { startY: e.clientY, startH: bottomH };
            document.body.style.cursor = "row-resize";
          }}
          title="Drag to resize canvas / bottom panel"
        >
          <div className="h-1 w-16 rounded-full bg-white/15 transition group-hover:bg-accent-cyan/60" />
        </div>

        <div className="min-h-0" style={{ height: bottomH }}>
          <BottomPanel logs={inv.logs} report={inv.report} question={question} />
        </div>
      </div>
    </div>
  );
}
