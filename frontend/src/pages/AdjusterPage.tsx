import { useEffect, useMemo, useState } from "react";
import ProcessPipeline from "../components/ProcessPipeline";
import { api } from "../lib/api";
import { useInvestigation } from "../hooks/useInvestigation";
import type { ClaimListItem, ClaimSummary } from "../types";

const PROCESS_Q =
  "Run a comprehensive full claim process from filing through report for human review. Include weather and required web research.";

function money(v: unknown): string {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "—";
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function AdjusterPage() {
  const [claims, setClaims] = useState<ClaimListItem[]>([]);
  const [claimId, setClaimId] = useState("CLM-1001");
  const [claim, setClaim] = useState<ClaimSummary | null>(null);
  const [question, setQuestion] = useState(PROCESS_Q);
  const [examples, setExamples] = useState<string[]>([]);
  const [reviewedNote, setReviewedNote] = useState("");
  const [localReviewed, setLocalReviewed] = useState(false);
  const inv = useInvestigation();

  useEffect(() => {
    api.claims().then(setClaims).catch(console.error);
  }, []);

  useEffect(() => {
    if (!claimId) {
      setClaim(null);
      return;
    }
    api.claim(claimId).then(setClaim).catch(console.error);
    api.exampleQuestions(claimId).then(setExamples).catch(() => undefined);
    setLocalReviewed(false);
    setReviewedNote("");
  }, [claimId]);

  const report = inv.report;
  const awaitingHuman =
    inv.handoff ||
    report?.investigation_status === "awaiting_human" ||
    report?.human_review_required;

  const estimateBits = useMemo(() => {
    const ea = report?.estimate_analysis || {};
    const fin = report?.illustrative_financials || {};
    return { ea, fin };
  }, [report]);

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-accent-cyan">
            Adjuster workspace
          </p>
          <h2 className="font-display text-2xl font-semibold text-white">Claim review desk</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Run the agentic claim process, then review the draft for a human decision. This screen
            never approves, denies, settles, or pays a claim.
          </p>
        </div>
        <label className="text-xs text-slate-400">
          Claim
          <select
            className="ml-2 rounded-lg border border-white/10 bg-navy-800 px-3 py-2 text-sm text-slate-100"
            value={claimId}
            onChange={(e) => setClaimId(e.target.value)}
          >
            {claims.map((c) => (
              <option key={c.claim_id} value={c.claim_id}>
                {c.claim_id} · {c.scenario_tag || "claim"}
              </option>
            ))}
          </select>
        </label>
      </header>

      <section className="rounded-xl border border-white/10 bg-navy-900/80 p-4">
        <label className="block text-xs font-medium text-slate-400" htmlFor="adjuster-question">
          Your question
        </label>
        <textarea
          id="adjuster-question"
          rows={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about this claim — e.g. market parts cost, estimate compare, weather at loss…"
          className="mt-2 w-full resize-y rounded-lg border border-white/10 bg-navy-800 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-accent-cyan/40 focus:outline-none"
        />
        <div className="mt-2 flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setQuestion(PROCESS_Q)}
            className="rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-400 hover:bg-white/5 hover:text-slate-200"
          >
            Full claim process
          </button>
          {examples.slice(0, 4).map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => setQuestion(ex)}
              className="max-w-full truncate rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-400 hover:bg-white/5 hover:text-slate-200"
              title={ex}
            >
              {ex}
            </button>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={inv.running || !claimId || !question.trim()}
            onClick={() => inv.start(claimId, question.trim())}
            className="rounded-lg bg-gradient-to-r from-accent-blue to-accent-violet px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {inv.running ? "Running…" : "Run"}
          </button>
          <span className="text-[11px] text-slate-500">
            Live Workflow mirrors this run for debugging · web/market search depends on your question
          </span>
        </div>
      </section>

      <ProcessPipeline
        currentStage={inv.currentStage}
        running={inv.running}
        handoff={Boolean(awaitingHuman && report)}
      />

      {inv.error && (
        <div className="rounded-lg border border-accent-red/40 bg-accent-red/10 px-4 py-3 text-sm text-accent-red">
          {inv.error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-5">
        <section className="space-y-3 rounded-xl border border-white/10 bg-navy-900/80 p-4 lg:col-span-2">
          <h3 className="font-display text-sm font-semibold text-white">Claim snapshot</h3>
          {claim ? (
            <dl className="space-y-2 text-sm text-slate-300">
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Claim</dt>
                <dd className="font-medium text-accent-cyan">{claim.claim_id}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Policy</dt>
                <dd>{claim.policy_number}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Insured</dt>
                <dd>{claim.insured_name}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Loss date</dt>
                <dd>{claim.accident_date}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Vehicle</dt>
                <dd className="text-right">
                  {claim.vehicle.year} {claim.vehicle.make} {claim.vehicle.model}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Location</dt>
                <dd>{claim.location}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Shop estimate (file)</dt>
                <dd>{money(claim.estimate_total)}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Collision deductible</dt>
                <dd>{money(claim.collision_deductible)}</dd>
              </div>
              <p className="rounded-lg border border-white/5 bg-navy-800/60 p-3 text-xs leading-relaxed text-slate-400">
                {claim.accident_description}
              </p>
              <div>
                <div className="text-xs text-slate-500">Submitted documents</div>
                <p className="mt-1 text-xs text-slate-300">
                  {claim.submitted_documents?.length
                    ? claim.submitted_documents.join(", ")
                    : "None listed"}
                </p>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-slate-500">Select a claim to begin.</p>
          )}
        </section>

        <section className="space-y-4 rounded-xl border border-white/10 bg-navy-900/80 p-4 lg:col-span-3">
          {!report && !inv.running && (
            <div className="rounded-lg border border-dashed border-white/15 bg-navy-800/40 px-4 py-10 text-center">
              <p className="font-display text-sm text-slate-300">No investigation report yet</p>
              <p className="mt-2 text-xs text-slate-500">
                Click <span className="text-slate-300">Run full claim process</span> to file,
                classify, investigate (including estimates / web research), and draft a report for
                your review.
              </p>
            </div>
          )}

          {inv.running && !report && (
            <div className="rounded-lg border border-accent-cyan/30 bg-accent-cyan/10 px-4 py-6 text-sm text-accent-cyan">
              Agent is working through the claim stages…
              {inv.currentStage ? ` Current stage: ${inv.currentStage}.` : ""}
            </div>
          )}

          {report && (
            <>
              {awaitingHuman && (
                <div className="rounded-lg border border-accent-amber/40 bg-accent-amber/10 p-4">
                  <div className="font-display text-sm font-semibold text-white">
                    Ready for human adjuster review
                  </div>
                  <p className="mt-1 text-xs text-slate-300">
                    Status: {report.investigation_status}. The agent did not approve, deny, settle,
                    or pay this claim.
                  </p>
                  {report.unresolved_questions?.length ? (
                    <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-300">
                      {report.unresolved_questions.map((q, i) => (
                        <li key={i}>{q}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              )}

              <div>
                <h3 className="font-display text-sm font-semibold text-white">Investigation summary</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-300">{report.claim_summary}</p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-white/10 bg-navy-800/50 p-3">
                  <div className="text-[11px] uppercase tracking-wide text-slate-500">
                    Illustrative financials
                  </div>
                  <pre className="mt-2 max-h-40 overflow-auto font-mono text-[11px] text-slate-300">
                    {JSON.stringify(estimateBits.fin, null, 2)}
                  </pre>
                </div>
                <div className="rounded-lg border border-white/10 bg-navy-800/50 p-3">
                  <div className="text-[11px] uppercase tracking-wide text-slate-500">
                    Estimate analysis
                  </div>
                  <pre className="mt-2 max-h-40 overflow-auto font-mono text-[11px] text-slate-300">
                    {JSON.stringify(estimateBits.ea, null, 2)}
                  </pre>
                </div>
              </div>

              <div>
                <h3 className="font-display text-sm font-semibold text-white">Coverage considerations</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">
                  {(report.coverage_considerations || []).length ? (
                    report.coverage_considerations.map((x, i) => <li key={i}>{x}</li>)
                  ) : (
                    <li className="list-none text-slate-500">None listed</li>
                  )}
                </ul>
              </div>

              <div>
                <h3 className="font-display text-sm font-semibold text-white">Evidence / citations</h3>
                <ul className="mt-2 space-y-2">
                  {(report.retrieved_evidence || []).length ? (
                    report.retrieved_evidence.map((c, i) => (
                      <li
                        key={i}
                        className="rounded-lg border border-white/5 bg-navy-800/50 p-3 text-xs text-slate-300"
                      >
                        <div className="text-accent-cyan">
                          {c.document_name}
                          {c.section ? ` · ${c.section}` : ""}
                        </div>
                        <p className="mt-1 text-slate-400">{c.excerpt}</p>
                      </li>
                    ))
                  ) : (
                    <li className="text-sm text-slate-500">No citations in this report.</li>
                  )}
                </ul>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <h3 className="font-display text-sm font-semibold text-white">Missing documents</h3>
                  <p className="mt-2 text-sm text-slate-300">
                    {report.missing_documents?.length
                      ? report.missing_documents.join(", ")
                      : "None flagged"}
                  </p>
                </div>
                <div>
                  <h3 className="font-display text-sm font-semibold text-white">Discrepancies</h3>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">
                    {(report.potential_discrepancies || []).length ? (
                      report.potential_discrepancies.map((x, i) => <li key={i}>{x}</li>)
                    ) : (
                      <li className="list-none text-slate-500">None flagged</li>
                    )}
                  </ul>
                </div>
              </div>

              <div>
                <h3 className="font-display text-sm font-semibold text-white">Recommended next steps</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">
                  {(report.recommended_next_steps || []).map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ul>
              </div>

              <div className="rounded-lg border border-white/10 bg-navy-800/40 p-4">
                <h3 className="font-display text-sm font-semibold text-white">
                  Adjuster action (human only)
                </h3>
                <p className="mt-1 text-xs text-slate-500">
                  Record that you reviewed the draft. Payment / coverage decisions stay outside this
                  demo system.
                </p>
                <textarea
                  className="mt-3 h-20 w-full resize-none rounded-lg border border-white/10 bg-navy-900 px-3 py-2 text-sm text-slate-100"
                  placeholder="Optional review notes for your file…"
                  value={reviewedNote}
                  onChange={(e) => setReviewedNote(e.target.value)}
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setLocalReviewed(true)}
                    className="rounded-lg border border-accent-green/40 bg-accent-green/15 px-3 py-2 text-xs font-medium text-accent-green"
                  >
                    Mark draft as reviewed
                  </button>
                  <button
                    type="button"
                    disabled
                    title="Out of scope — licensed adjuster systems only"
                    className="cursor-not-allowed rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-500"
                  >
                    Approve / deny / pay (disabled)
                  </button>
                </div>
                {localReviewed && (
                  <p className="mt-2 text-xs text-accent-green">
                    Review noted locally for this session
                    {reviewedNote.trim() ? " (notes saved in UI only)." : "."}
                  </p>
                )}
              </div>

              <p className="rounded-lg border border-accent-amber/25 bg-accent-amber/5 p-3 text-xs text-accent-amber">
                {report.disclaimer ||
                  "Human review required. This system never approves, denies, settles, or pays claims."}
              </p>
            </>
          )}
        </section>
      </div>

      <p className="text-center text-[11px] text-slate-600">
        Need the technical canvas? Open the <span className="text-slate-400">Live Workflow</span>{" "}
        tab. Adjuster Desk is for review, not engineering debug.
      </p>
    </div>
  );
}
