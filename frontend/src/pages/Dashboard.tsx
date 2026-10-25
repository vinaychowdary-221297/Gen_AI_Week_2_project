import { useState } from "react";
import WorkflowCanvas from "../components/WorkflowCanvas";
import NodeInspector from "../components/NodeInspector";
import { useInvestigation } from "../hooks/useInvestigation";

export default function Dashboard() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const inv = useInvestigation();

  const statusLabel = inv.error
    ? inv.error
    : inv.running
      ? "Live — reflecting Adjuster Desk run"
      : inv.runId
        ? "Last run from Adjuster Desk"
        : "Start a run on Adjuster Desk to watch the flow here";

  return (
    <div className="mx-auto flex h-[calc(100vh-72px)] max-w-[1800px] flex-col gap-2 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/10 bg-navy-900/80 px-3 py-2">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wide text-accent-cyan">
            Live workflow · debug
          </p>
          <p className={`text-xs ${inv.error ? "text-accent-red" : "text-slate-400"}`}>
            {statusLabel}
            {inv.claimId ? ` · ${inv.claimId}` : ""}
            {inv.currentStage ? ` · ${inv.currentStage}` : ""}
            {" · click a node for input / output / logs"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setResetKey((k) => k + 1)}
          className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-slate-300 hover:bg-white/5"
        >
          Reset layout
        </button>
      </div>

      <div className="flex min-h-0 flex-1 gap-3">
        <div className="min-h-0 min-w-0 flex-1">
          <WorkflowCanvas
            nodeState={inv.nodeState}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
            resetKey={resetKey}
            activeEdgeIds={inv.activeEdgeIds}
            traversedEdgeIds={inv.traversedEdgeIds}
            minimal
          />
        </div>
        {selectedNodeId ? (
          <div className="w-[320px] shrink-0 min-h-0">
            <NodeInspector
              nodeId={selectedNodeId}
              execution={inv.nodeState[selectedNodeId]}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
