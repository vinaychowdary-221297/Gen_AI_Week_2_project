import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { ClaimListItem } from "../types";

export default function ClaimsPage() {
  const [claims, setClaims] = useState<ClaimListItem[]>([]);

  useEffect(() => {
    api.claims().then(setClaims).catch(console.error);
  }, []);

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h2 className="font-display text-xl font-semibold">Synthetic Claims</h2>
      <p className="mt-1 text-sm text-slate-400">
        15 fictional claims across 5 policies. CLM-1001 is the primary demo scenario.
      </p>
      <div className="mt-6 overflow-hidden rounded-xl border border-white/10">
        <table className="w-full text-left text-sm">
          <thead className="bg-navy-800 text-slate-400">
            <tr>
              <th className="px-4 py-3 font-medium">Claim</th>
              <th className="px-4 py-3 font-medium">Policy</th>
              <th className="px-4 py-3 font-medium">Date</th>
              <th className="px-4 py-3 font-medium">Vehicle</th>
              <th className="px-4 py-3 font-medium">Scenario</th>
              <th className="px-4 py-3 font-medium">Estimate</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((c) => (
              <tr key={c.claim_id} className="border-t border-white/5 text-slate-300">
                <td className="px-4 py-3 font-medium text-accent-cyan">{c.claim_id}</td>
                <td className="px-4 py-3">{c.policy_id}</td>
                <td className="px-4 py-3">{c.accident_date}</td>
                <td className="px-4 py-3">
                  {c.vehicle.year} {c.vehicle.make} {c.vehicle.model}
                </td>
                <td className="px-4 py-3">{c.scenario_tag || "—"}</td>
                <td className="px-4 py-3">${c.estimate_total.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
