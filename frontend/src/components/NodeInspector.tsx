import { useState } from "react";
import type { NodeExecution } from "../types";

interface Props {
  nodeId: string | null;
  execution?: NodeExecution;
}

export default function NodeInspector({ nodeId, execution }: Props) {
  const [tab, setTab] = useState<"input" | "output" | "logs">("output");

  if (!nodeId) {
    return (
      <div className="flex h-full flex-col rounded-xl border border-white/10 bg-navy-900/80 p-4">
        <h3 className="font-display text-sm font-semibold text-slate-100">Node Inspector</h3>
        <p className="mt-3 text-sm text-slate-400">
          Click a workflow node to inspect inputs, outputs, duration, and logs.
        </p>
      </div>
    );
  }

  const status = execution?.status || "idle";

  return (
    <div className="flex h-full flex-col rounded-xl border border-white/10 bg-navy-900/80">
      <div className="border-b border-white/10 p-4">
        <h3 className="font-display text-sm font-semibold text-slate-100">Node Inspector</h3>
        <div className="mt-2 text-xs text-slate-400">
          <div>
            <span className="text-slate-500">Node:</span> {nodeId}
          </div>
          <div>
            <span className="text-slate-500">Status:</span>{" "}
            <span
              className={
                status === "completed"
                  ? "text-accent-green"
                  : status === "running"
                    ? "text-accent-blue"
                    : status === "failed"
                      ? "text-accent-red"
                      : "text-slate-300"
              }
            >
              {status}
            </span>
          </div>
          {execution?.duration_ms != null && (
            <div>
              <span className="text-slate-500">Duration:</span> {Math.round(execution.duration_ms)} ms
            </div>
          )}
          {execution?.error && (
            <div className="mt-2 rounded bg-accent-red/10 p-2 text-accent-red">{execution.error}</div>
          )}
        </div>
        <div className="mt-3 flex gap-1">
          {(["input", "output", "logs"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-md px-2.5 py-1 text-xs capitalize ${
                tab === t ? "bg-accent-blue/20 text-accent-cyan" : "text-slate-400 hover:bg-white/5"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      <div className="scrollbar-thin flex-1 overflow-auto p-3 font-mono text-[11px] text-slate-300">
        {tab === "input" && (
          <pre className="whitespace-pre-wrap break-words">
            {JSON.stringify(execution?.input ?? null, null, 2)}
          </pre>
        )}
        {tab === "output" && (
          <pre className="whitespace-pre-wrap break-words">
            {JSON.stringify(execution?.output ?? null, null, 2)}
          </pre>
        )}
        {tab === "logs" && (
          <div className="space-y-2">
            {(execution?.history || []).length === 0 && (
              <div className="text-slate-500">No execution events yet for this node.</div>
            )}
            {(execution?.history || []).map((ev) => (
              <div key={ev.event_id} className="rounded border border-white/5 bg-navy-800/80 p-2">
                <div className="text-accent-cyan">{ev.event_type}</div>
                <div className="text-slate-500">{ev.timestamp}</div>
                {ev.duration_ms != null && <div>duration: {Math.round(ev.duration_ms)} ms</div>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
