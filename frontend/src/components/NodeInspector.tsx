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
        <h3 className="font-display text-sm font-semibold text-slate-100">Node I/O</h3>
        <p className="mt-3 text-sm text-slate-400">Click a node to see input, output, and logs.</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-white/10 bg-navy-900/80">
      <div className="border-b border-white/10 p-3">
        <div className="truncate font-mono text-xs text-accent-cyan">{nodeId}</div>
        <div className="mt-2 flex gap-1">
          {(["input", "output", "logs"] as const).map((t) => (
            <button
              key={t}
              type="button"
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
              <div className="text-slate-500">No logs for this node yet.</div>
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
