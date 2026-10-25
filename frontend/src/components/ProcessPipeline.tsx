export type ProcessStage =
  | "filing"
  | "classification"
  | "investigation"
  | "report"
  | "human_review"
  | null;

const STAGES: { id: ProcessStage; label: string; hint: string }[] = [
  { id: "filing", label: "1. Filing", hint: "FNOL / claim intake" },
  { id: "classification", label: "2. Classify", hint: "Loss type & severity" },
  { id: "investigation", label: "3. Investigate", hint: "RAG · estimates · web" },
  { id: "report", label: "4. Report", hint: "Structured draft" },
  { id: "human_review", label: "5. Human Review", hint: "Adjuster decision" },
];

interface Props {
  currentStage: ProcessStage;
  running: boolean;
  handoff?: boolean;
}

export default function ProcessPipeline({ currentStage, running, handoff }: Props) {
  const order = STAGES.map((s) => s.id);
  const currentIdx = currentStage ? order.indexOf(currentStage) : -1;

  return (
    <div className="rounded-xl border border-white/10 bg-navy-900/80 px-3 py-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <h3 className="font-display text-xs font-semibold uppercase tracking-wide text-slate-300">
            Claim process pipeline
          </h3>
          <p className="text-[11px] text-slate-500">
            Week 3 single-agent stages · lights up as the run progresses
          </p>
        </div>
        {handoff ? (
          <span className="rounded-full border border-accent-amber/40 bg-accent-amber/15 px-2 py-0.5 text-[10px] font-medium text-accent-amber">
            Awaiting human
          </span>
        ) : running ? (
          <span className="rounded-full border border-accent-cyan/40 bg-accent-cyan/15 px-2 py-0.5 text-[10px] font-medium text-accent-cyan">
            Running
          </span>
        ) : null}
      </div>
      <div className="flex flex-wrap items-stretch gap-2">
        {STAGES.map((stage, i) => {
          const done = currentIdx > i;
          const active = currentIdx === i;
          return (
            <div key={stage.id} className="flex min-w-[110px] flex-1 items-center gap-2">
              <div
                className={`flex-1 rounded-lg border px-2.5 py-2 transition ${
                  active
                    ? "border-accent-cyan/50 bg-accent-cyan/15 shadow-[0_0_20px_rgba(34,211,238,0.15)]"
                    : done
                      ? "border-accent-green/30 bg-accent-green/10"
                      : "border-white/10 bg-navy-800/50"
                }`}
              >
                <div
                  className={`text-[11px] font-semibold ${
                    active ? "text-accent-cyan" : done ? "text-accent-green" : "text-slate-400"
                  }`}
                >
                  {stage.label}
                </div>
                <div className="mt-0.5 text-[10px] text-slate-500">{stage.hint}</div>
              </div>
              {i < STAGES.length - 1 ? (
                <span className="hidden text-slate-600 sm:inline" aria-hidden>
                  →
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
