# Insurance Claims Intelligence

Local **Agentic Hybrid RAG** app for insurance claim investigation. A LangGraph agent calls deterministic tools and (when needed) hybrid policy retrieval, streams execution to a React Flow canvas over SSE, and writes a structured report for human review.

**Cloud only:** Nebius Token Factory (chat + embeddings) and Pinecone (dense vectors). Everything else runs on your machine.

The system never approves, denies, settles, or pays claims.

**What we built (overview, data, prompts, iterations, learnings):** [PROJECT_REPORT.docx](PROJECT_REPORT.docx)  
**Windows setup / troubleshooting:** [SETUP_WINDOWS.md](SETUP_WINDOWS.md)

---

## Quick start (Windows)

### 1. Prerequisites

| Tool | Check |
| --- | --- |
| [uv](https://docs.astral.sh/uv/) | `uv --version` |
| Node.js 18+ | `node -v` / `npm -v` |
| Nebius API key | Token Factory console |
| Pinecone API key | Pinecone console |

### 2. One-time setup

From the **project root** (folder that contains `dev.ps1`):

```powershell
# Credentials
Copy-Item backend\.env.example backend\.env
# Edit backend\.env — set Nebius + Pinecone keys and real model IDs from your Nebius catalog

# Python deps, synthetic data, hybrid indexes
cd backend
uv sync
uv run python scripts\generate_data.py
uv run python scripts\ingest_docs.py
cd ..
```

`ingest_docs.py` builds local BM25 and upserts policy chunks to Pinecone. It needs valid Nebius + Pinecone credentials.

### 3. Run the app

```powershell
.\dev.ps1
```

| Service | URL |
| --- | --- |
| UI | http://127.0.0.1:5173 |
| API health | http://127.0.0.1:8000/api/health |
| OpenAPI | http://127.0.0.1:8000/docs |

Stop with `Ctrl+C` in the same terminal.

Later starts (skip dep sync):

```powershell
.\dev.ps1 -SkipSync
```

Or run API and UI in separate terminals:

```powershell
.\scripts\dev-backend.ps1
.\scripts\dev-frontend.ps1
```

### 4. Try a demo

1. Open the UI and confirm status lights (Backend / Nebius / Pinecone / BM25) are green.
2. Select claim **CLM-1001**.
3. Keep the default question (or pick an example).
4. Click **Run Investigation**.
5. Watch the canvas; open **Investigation Report** when finished.

---

## What it does

- **Claim-scoped** investigation (pick a claim ID) or **portfolio** questions (claim ID = none)
- Hybrid RAG over policy Markdown: **BM25 + Nebius embeddings + Pinecone + RRF**
- Deterministic tools for dates, listed coverages, estimate math, missing docs, similar claims, and portfolio stats
- Live workflow canvas driven by real tool/SSE events
- Investigation report with answer summary, citations, and human-review required

### Architecture

```
UI (React + React Flow)
  → FastAPI (/api/investigate + SSE)
    → LangGraph agent (Nebius chat)
      → Tools
           ├─ Local claims / policies JSON
           ├─ query_portfolio_data (book-level)
           ├─ Hybrid RAG (BM25 + Pinecone + RRF)
           └─ generate_investigation_report
```

### Agent tools

| Tool | Purpose | Uses RAG? |
| --- | --- | --- |
| `get_claim_details` | Claim + linked policy intake | No |
| `search_policy_documents` | Policy text retrieval (BM25 + dense + RRF) | **Yes** |
| `validate_policy_dates` | Loss date vs effective/expiration | No |
| `check_coverage_facts` | Listed coverages + deductibles | No |
| `analyze_repair_estimate` | Decimal line-item math + duplicate flags | No |
| `check_missing_documents` | Required-doc checklist gaps | No |
| `find_similar_claims` | Keyword/tag similarity over claims JSON | No |
| `query_portfolio_data` | Counts/lists across all policies & claims | No |
| `generate_investigation_report` | Final structured report for the UI | No |

RAG runs when the question needs **policy document language** for a known `policy_id`. Portfolio questions (no claim selected) use `query_portfolio_data`, not RAG.

### Using the UI

- **Claim selected** — claim-scoped tools + optional policy RAG; answer appears in the report summary.
- **Claim = None (portfolio)** — book-level questions via `query_portfolio_data` (e.g. active policy counts). Do not expect a settlement or “amount to pay” decision.

---

## Data

Under `backend/data/`:

- Policies (JSON + Markdown), claims, claim documents, repair line items, required-document checklists
- BM25 index under `backend/data/indexes/`
- Evaluation questions under `backend/data/evaluation_questions.json`

Regenerate synthetic data:

```powershell
cd backend
uv run python scripts\generate_data.py
```

BM25 only (no cloud keys):

```powershell
uv run python scripts\build_bm25_only.py
```

Full hybrid ingest (Nebius + Pinecone):

```powershell
uv run python scripts\ingest_docs.py
```

---

## Tests & evaluation

```powershell
cd backend
uv run pytest -q
uv run python scripts\evaluate.py
```

---

## Project layout

```
backend/
  app/                 # FastAPI, LangGraph agent, RAG, Nebius/Pinecone clients
  data/                # JSON/CSV + policy Markdown + indexes
  scripts/             # generate / ingest / evaluate
  tests/
  pyproject.toml       # uv project
frontend/
  src/                 # React + TypeScript + React Flow
scripts/
  run_app.py           # Starts API + UI together
  dev-backend.ps1
  dev-frontend.ps1
dev.ps1                # One-command local run
SETUP_WINDOWS.md       # Detailed Windows setup + troubleshooting
PROJECT_REPORT.docx    # What we built: overview, data, prompts, iterations
```

---

## Safety notes

- Policy-date membership is not a legal coverage determination
- “Coverage listed” is not a coverage decision
- Estimate nets are illustrative only
- Duplicate line items are flagged, never auto-removed
- Payment / settlement amounts are out of scope; final decisions need a licensed human adjuster
