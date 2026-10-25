import { NavLink } from "react-router-dom";
import type { HealthStatus } from "../types";

interface Props {
  health: HealthStatus | null;
}

function Dot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-navy-800/80 px-2.5 py-1 text-[11px] text-slate-300">
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-accent-green" : "bg-accent-red"}`} />
      {label}
    </span>
  );
}

export default function TopNav({ health }: Props) {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-1.5 text-sm transition ${
      isActive ? "bg-white/10 text-white" : "text-slate-400 hover:text-slate-200"
    }`;

  return (
    <header className="border-b border-white/10 bg-navy-900/70 backdrop-blur">
      <div className="mx-auto flex max-w-[1800px] items-center justify-between gap-4 px-4 py-3">
        <div>
          <h1 className="font-display text-lg font-semibold tracking-tight text-white">
            Insurance Claims Intelligence
          </h1>
          <p className="text-xs text-slate-400">
            Week 3 · Filing → Classify → Investigate → Report → Human Review · Keenable web search
          </p>
        </div>
        <nav className="flex flex-wrap items-center gap-1">
          <NavLink to="/" className={linkClass} end>
            Adjuster Desk
          </NavLink>
          <NavLink to="/workflow" className={linkClass}>
            Live Workflow
          </NavLink>
          <NavLink to="/claims" className={linkClass}>
            Claims
          </NavLink>
          <NavLink to="/documents" className={linkClass}>
            Documents
          </NavLink>
          <NavLink to="/evaluation" className={linkClass}>
            Evaluation
          </NavLink>
        </nav>
        <div className="flex flex-wrap items-center gap-2">
          <Dot ok={!!health?.backend?.ok} label="Backend" />
          <Dot ok={!!health?.nebius?.ok} label="Nebius" />
          <Dot ok={!!health?.pinecone?.ok} label="Pinecone" />
          <Dot ok={!!health?.keenable?.ok} label="Keenable" />
          <Dot ok={!!health?.bm25?.ok} label="BM25" />
        </div>
      </div>
    </header>
  );
}
