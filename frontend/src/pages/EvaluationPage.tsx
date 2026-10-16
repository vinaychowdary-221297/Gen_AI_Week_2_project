import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function EvaluationPage() {
  const [questions, setQuestions] = useState<Array<Record<string, unknown>>>([]);

  useEffect(() => {
    api.evaluationQuestions().then(setQuestions).catch(console.error);
  }, []);

  return (
    <div className="mx-auto max-w-5xl p-6">
      <h2 className="font-display text-xl font-semibold">Evaluation Set</h2>
      <p className="mt-1 text-sm text-slate-400">
        20 gold questions for offline evaluation. Run{" "}
        <code className="text-accent-cyan">pytest</code> and{" "}
        <code className="text-accent-cyan">python scripts/evaluate.py</code> from the backend.
      </p>
      <div className="mt-6 space-y-3">
        {questions.map((q) => (
          <div key={String(q.id)} className="rounded-xl border border-white/10 bg-navy-900/70 p-4">
            <div className="text-xs text-accent-cyan">
              {String(q.id)} · {String(q.claim_id)}
            </div>
            <div className="mt-1 text-sm text-slate-200">{String(q.question)}</div>
            <div className="mt-2 text-[11px] text-slate-500">
              Expected contains: {JSON.stringify(q.expected_contains)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
