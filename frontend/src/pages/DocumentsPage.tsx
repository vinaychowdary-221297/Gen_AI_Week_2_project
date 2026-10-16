export default function DocumentsPage() {
  return (
    <div className="mx-auto max-w-4xl p-6">
      <h2 className="font-display text-xl font-semibold">Policy Documents</h2>
      <p className="mt-2 text-sm leading-relaxed text-slate-400">
        Synthetic personal auto policies live in <code className="text-accent-cyan">backend/data/policies/</code>.
        Each Markdown file is chunked, embedded via Nebius, indexed in Pinecone, and mirrored in the local BM25
        store. Re-run ingestion after changing policy text:
      </p>
      <pre className="mt-4 overflow-auto rounded-xl border border-white/10 bg-navy-900 p-4 text-xs text-slate-300">
{`cd backend
.\\venv\\Scripts\\Activate.ps1
python scripts\\generate_data.py
python scripts\\ingest_docs.py`}
      </pre>
      <ul className="mt-6 list-disc space-y-2 pl-5 text-sm text-slate-300">
        <li>POL-5001 — Avery Chen / TX / Toyota RAV4 (CLM-1001)</li>
        <li>POL-5002 — Jordan Blake / CA / Honda Civic (no collision)</li>
        <li>POL-5003 — Samira Ortiz / FL / Ford Escape</li>
        <li>POL-5004 — Morgan Ellis / NY / Subaru Outback (expired)</li>
        <li>POL-5005 — Riley Nguyen / IL / Tesla Model Y</li>
      </ul>
    </div>
  );
}
