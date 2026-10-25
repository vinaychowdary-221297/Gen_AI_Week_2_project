import { useState } from "react";
import type { InvestigationReport, WorkflowEvent } from "../types";

interface Props {
  logs: WorkflowEvent[];
  report: InvestigationReport | null;
  question?: string;
}

export default function BottomPanel({ logs, report, question }: Props) {
  const [tab, setTab] = useState<"logs" | "report">("logs");

  return (
    <div className="flex h-full flex-col rounded-xl border border-white/10 bg-navy-900/80">
      <div className="flex items-center gap-2 border-b border-white/10 px-4 py-2">
        <button
          onClick={() => setTab("logs")}
          className={`rounded px-3 py-1 text-xs font-medium ${
            tab === "logs" ? "bg-white/10 text-white" : "text-slate-400"
          }`}
        >
          Execution Logs
        </button>
        <button
          onClick={() => setTab("report")}
          className={`rounded px-3 py-1 text-xs font-medium ${
            tab === "report" ? "bg-white/10 text-white" : "text-slate-400"
          }`}
        >
          Investigation Report
        </button>
      </div>
      <div className="scrollbar-thin flex-1 overflow-auto p-3 text-xs">
        {tab === "logs" && (
          <table className="w-full text-left">
            <thead className="text-slate-500">
              <tr>
                <th className="pb-2 pr-3 font-medium">Time</th>
                <th className="pb-2 pr-3 font-medium">Event</th>
                <th className="pb-2 pr-3 font-medium">Node</th>
                <th className="pb-2 pr-3 font-medium">Status</th>
                <th className="pb-2 font-medium">Duration</th>
              </tr>
            </thead>
            <tbody>
              {logs
                .filter((l) => l.event_type !== "heartbeat")
                .slice(-80)
                .map((l) => (
                  <tr key={l.event_id} className="border-t border-white/5 text-slate-300">
                    <td className="py-1.5 pr-3 font-mono text-[10px] text-slate-500">
                      {new Date(l.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="py-1.5 pr-3 text-accent-cyan">{l.event_type}</td>
                    <td className="py-1.5 pr-3">{l.node_id || "—"}</td>
                    <td className="py-1.5 pr-3">{l.status}</td>
                    <td className="py-1.5">
                      {l.duration_ms != null ? `${Math.round(l.duration_ms)} ms` : "—"}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}

        {tab === "report" && !report && (
          <div className="text-slate-500">Run an investigation to generate a grounded report.</div>
        )}

        {tab === "report" && report && (
          <div className="space-y-4 text-slate-300">
            {(report.investigation_status === "awaiting_human" ||
              report.human_review_required) && (
              <div className="rounded border border-accent-amber/40 bg-accent-amber/10 p-3 text-accent-amber">
                <div className="font-semibold text-white">Awaiting human adjuster</div>
                <p className="mt-1 text-slate-300">
                  Autonomous processing ended. No approval, denial, settlement, or payment was made.
                </p>
                {report.unresolved_questions?.length ? (
                  <ul className="mt-2 list-disc pl-5 text-slate-300">
                    {report.unresolved_questions.map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            )}
            <section>
              {question ? (
                <>
                  <h4 className="font-display text-sm text-white">Question</h4>
                  <p className="mt-1 text-slate-400">{question}</p>
                </>
              ) : null}
              <h4 className={`font-display text-sm text-white ${question ? "mt-3" : ""}`}>
                Answer / Summary
              </h4>
              <p className="mt-1 leading-relaxed">{report.claim_summary}</p>
              <p className="mt-1 text-accent-amber">Status: {report.investigation_status}</p>
            </section>
            <section>
              <h4 className="font-display text-sm text-white">Evidence</h4>
              <ul className="mt-1 space-y-2">
                {report.retrieved_evidence?.length ? (
                  report.retrieved_evidence.map((c, i) => (
                    <li key={i} className="rounded border border-white/5 bg-navy-800/50 p-2">
                      <div className="text-accent-cyan">
                        {c.document_name}
                        {c.section ? ` · ${c.section}` : ""}
                        {c.page_number != null ? ` · p.${c.page_number}` : ""}
                      </div>
                      <div className="mt-1 text-slate-400">{c.excerpt}</div>
                    </li>
                  ))
                ) : (
                  <li className="text-slate-500">No citations returned.</li>
                )}
              </ul>
            </section>
            <section>
              <h4 className="font-display text-sm text-white">Coverage considerations</h4>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {report.coverage_considerations?.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </section>
            <section>
              <h4 className="font-display text-sm text-white">Calculations</h4>
              <pre className="mt-1 overflow-auto rounded bg-navy-800/60 p-2 font-mono text-[11px]">
                {JSON.stringify(
                  {
                    estimate_analysis: report.estimate_analysis,
                    illustrative_financials: report.illustrative_financials,
                  },
                  null,
                  2
                )}
              </pre>
            </section>
            <section>
              <h4 className="font-display text-sm text-white">Missing documents</h4>
              <p className="mt-1">
                {report.missing_documents?.length
                  ? report.missing_documents.join(", ")
                  : "None flagged"}
              </p>
            </section>
            <section>
              <h4 className="font-display text-sm text-white">Next steps</h4>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {report.recommended_next_steps?.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </section>
            <p className="rounded border border-accent-amber/30 bg-accent-amber/10 p-2 text-accent-amber">
              {report.disclaimer ||
                "Human review required. This system never approves, denies, settles, or pays claims."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
