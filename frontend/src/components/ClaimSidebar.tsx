import type { ClaimSummary } from "../types";

interface Props {
  claimIds: string[];
  selectedClaimId: string;
  onSelectClaim: (id: string) => void;
  claim?: ClaimSummary | null;
  question: string;
  onQuestionChange: (q: string) => void;
  examples: string[];
  onRun: () => void;
  running: boolean;
}

export default function ClaimSidebar({
  claimIds,
  selectedClaimId,
  onSelectClaim,
  claim,
  question,
  onQuestionChange,
  examples,
  onRun,
  running,
}: Props) {
  return (
    <aside className="scrollbar-thin flex h-full flex-col gap-3 overflow-auto rounded-xl border border-white/10 bg-navy-900/80 p-4">
      <div>
        <h3 className="font-display text-sm font-semibold">Claim Process Agent</h3>
        <p className="mt-1 text-xs text-slate-400">
          Filing → classify → investigate (RAG + estimates + web) → report → human review.
        </p>
      </div>

      <label className="block text-xs text-slate-400">
        Claim ID
        <select
          className="mt-1 w-full rounded-lg border border-white/10 bg-navy-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-accent-blue"
          value={selectedClaimId}
          onChange={(e) => onSelectClaim(e.target.value)}
        >
          <option value="">— None (portfolio / generic) —</option>
          {claimIds.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </label>
      {!selectedClaimId && (
        <p className="rounded-md border border-accent-cyan/20 bg-accent-cyan/5 px-2 py-1.5 text-[11px] text-slate-400">
          No claim selected — ask book-of-business questions (e.g. how many policies are active).
        </p>
      )}

      {claim && (
        <div className="space-y-2 rounded-lg border border-white/5 bg-navy-800/60 p-3 text-xs text-slate-300">
          <div>
            <span className="text-slate-500">Policy:</span> {claim.policy_number}
          </div>
          <div>
            <span className="text-slate-500">Insured:</span> {claim.insured_name}
          </div>
          <div>
            <span className="text-slate-500">Vehicle:</span> {claim.vehicle.year} {claim.vehicle.make}{" "}
            {claim.vehicle.model} {claim.vehicle.trim}
          </div>
          <div>
            <span className="text-slate-500">Accident date:</span> {claim.accident_date}
          </div>
          <div>
            <span className="text-slate-500">Status:</span> {claim.claim_status}
          </div>
          <p className="leading-relaxed text-slate-400">{claim.accident_description}</p>
        </div>
      )}

      <label className="block text-xs text-slate-400">
        Investigation question
        <textarea
          className="mt-1 h-28 w-full resize-none rounded-lg border border-white/10 bg-navy-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-accent-violet"
          value={question}
          onChange={(e) => onQuestionChange(e.target.value)}
        />
      </label>

      {selectedClaimId ? (
        <button
          type="button"
          onClick={() =>
            onQuestionChange(
              "Run the full claim process from filing through report for human review."
            )
          }
          className="rounded-lg border border-accent-cyan/40 bg-accent-cyan/10 px-3 py-2 text-xs font-medium text-accent-cyan hover:bg-accent-cyan/20"
        >
          Load full claim process prompt
        </button>
      ) : null}

      <button
        onClick={onRun}
        disabled={running || !question.trim()}
        className="rounded-lg bg-gradient-to-r from-accent-blue to-accent-violet px-4 py-2.5 text-sm font-semibold text-white shadow-glow transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {running
          ? "Running…"
          : selectedClaimId
            ? "Run Claim Process / Investigation"
            : "Ask Portfolio Question"}
      </button>

      <div>
        <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          Example questions
        </div>
        <div className="space-y-1.5">
          {examples.slice(0, 6).map((ex) => (
            <button
              key={ex}
              onClick={() => onQuestionChange(ex)}
              className="block w-full rounded-md border border-white/5 bg-navy-800/40 px-2 py-1.5 text-left text-[11px] text-slate-400 hover:border-accent-cyan/40 hover:text-slate-200"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
