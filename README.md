# Insurance Claims Intelligence (Weeks 2–4)

Local **single-agent claim process** built on Week 2 **Agentic Hybrid RAG**. One LangGraph agent runs a claim through **Filing → Classification → Investigation → Report → Human Review**, with **Keenable** web search (weather + market parts/labor) and **preliminary vs facility** estimate comparison.

The system **never** approves, denies, settles, or pays claims.

| Week | Focus |
| --- | --- |
| **2** | Agentic Hybrid RAG (BM25 + dense/Pinecone + RRF) + tool-calling investigation agent |
| **3** | Single-agent claim process (+ Keenable, prelim vs facility estimates, Adjuster Desk / Live Workflow) |
| **4** | Own use-case evaluation — 40-case golden set, live baseline → fixes → improved scores |

| Doc | Purpose |
| --- | --- |
| [SETUP_WINDOWS.md](SETUP_WINDOWS.md) | Full Windows setup & troubleshooting |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture |
| [docs/WEEK3_AGENTIC.md](docs/WEEK3_AGENTIC.md) | Week 3 stages, tools, Keenable, demo claims |
| [docs/WEEK4_EVAL.md](docs/WEEK4_EVAL.md) | Week 4 evaluation report |
| [docs/PROJECT_REPORT.docx](docs/PROJECT_REPORT.docx) | Cumulative project report (Weeks 2–4) |
| [docs/WEEK4_PROJECT_REPORT.docx](docs/WEEK4_PROJECT_REPORT.docx) | Week 4 solution / evaluation Word report |
| [docs/WEEK3_DEMO_SCRIPTS.docx](docs/WEEK3_DEMO_SCRIPTS.docx) | Week 3 demo / Loom scripts |
| [docs/WEEK4_DEMO_SCRIPTS.docx](docs/WEEK4_DEMO_SCRIPTS.docx) | Week 4 demo / Loom scripts |
| [docs/week4/week4_eval_results.csv](docs/week4/week4_eval_results.csv) | Week 4 scored spreadsheet |

---

## How to run the application (normal use)

Day-to-day: start the API + frontend with `dev.ps1`. Full first-time setup is below (also in [SETUP_WINDOWS.md](SETUP_WINDOWS.md)).

### Already set up — run without downloading packages

If `backend\.venv` and `frontend\node_modules` already exist (and `backend\.env` is configured), start without `uv sync` / `npm install`:

```powershell
# From repo root ("week 2 Project")
.\dev.ps1 -SkipSync
```

That only launches the API + Vite UI — no package download.

Manual start (same idea — no sync):

```powershell
# Terminal 1 — API
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — UI
cd frontend
npm run dev
```

| URL | View |
| --- | --- |
| http://127.0.0.1:5173 | **Adjuster Desk** — pick a claim, ask a question, Run, review draft report |
| http://127.0.0.1:5173/workflow | **Live Workflow** — debug canvas; click a node → input / output / logs |
| http://127.0.0.1:8000/api/health | API health |

Stop with `Ctrl+C` in the terminal that launched the app.

### First-time setup (install packages + data)

```powershell
# From repo root ("week 2 Project")
Copy-Item backend\.env.example backend\.env
# Edit backend\.env — set Nebius, Pinecone, Keenable keys (see below)

cd backend
uv sync
uv run python scripts\generate_data.py
uv run python scripts\ingest_docs.py
cd ..
.\dev.ps1
```

`.\dev.ps1` (without `-SkipSync`) also runs `uv sync` and installs frontend deps if `node_modules` is missing.

### Required `.env` keys (`backend\.env`)

| Variable | Purpose |
| --- | --- |
| `NEBIUS_API_KEY` | Chat + embeddings (Token Factory) |
| `NEBIUS_CHAT_MODEL` | Tool-calling chat model (e.g. `openai/gpt-oss-120b`) |
| `NEBIUS_EMBED_MODEL` | Same embed model used at ingest (e.g. `Qwen/Qwen3-Embedding-8B`) |
| `PINECONE_API_KEY` / `PINECONE_INDEX` | Dense policy vectors |
| `KEENABLE_API_KEY` | Week 3 web / weather / market search (`keen_…`) |

Useful Week 3 knobs (optional):

```env
KEENABLE_MAX_RESULTS=5
KEENABLE_SEARCH_MODE=pro
KEENABLE_MARKET_LINE_LIMIT=5
MAX_TOOL_CALLS=28
AGENT_TIMEOUT_SECONDS=300
```

After changing data or policies, re-run from `backend\`:

```powershell
uv run python scripts\generate_data.py
uv run python scripts\ingest_docs.py
```

### Typical demo claims (in the UI)

1. **CLM-1001** — full claim process → prelim vs facility → human review  
2. **CLM-1013** — vandalism / comprehensive; estimate totals match tools  
3. **CLM-1004** — weather at loss → `search_web`  
4. **CLM-1005** — duplicate ADAS lines  
5. **CLM-1003** — expired policy → classification / human path  

More: [docs/WEEK3_AGENTIC.md](docs/WEEK3_AGENTIC.md) · troubleshooting: [SETUP_WINDOWS.md](SETUP_WINDOWS.md)

---

## Week 2 — Agentic Hybrid RAG

- FastAPI + React / React Flow  
- LangGraph tool-calling agent (Nebius)  
- Hybrid policy retrieval: local BM25 + Nebius embeddings + Pinecone + RRF  
- Deterministic tools: claim intake, dates, coverage flags, estimate math, missing docs, similar claims, portfolio  
- SSE live workflow canvas + investigation report UI  
- Safety: `human_review_required`; illustrative financials only  

## Week 3 — Single-agent claim process

Built on Week 2. **One** agent with stages — not multi-agent.

- Stages: Filing → Classification → Investigation → Report → Human Review  
- Tools: `classify_claim`, estimate parse/build/compare, Keenable `search_web` + market research, `request_human_handoff`  
- Preliminary (desk) vs facility (shop) estimates; money verified in code (Decimal)  
- Adjuster Desk + Live Workflow (shared run state)  

Details: [docs/WEEK3_AGENTIC.md](docs/WEEK3_AGENTIC.md)

## Week 4 — Own use-case evaluation

Evaluates the **same running agent** (not a separate app) with a labeled golden set (spreadsheet track).

| Item | Detail |
| --- | --- |
| Golden set | 40 cases (`backend/data/week4_golden_cases.json`) |
| Metrics | quality, safety, estimate fidelity, latency, overall pass rate |
| Live baseline | **33/40 PASS (82.5%)** |
| Live improved | **40/40 PASS (100%)** |
| Delta | +7 fixed; 0 regressions |

Optional — re-run live scoring (needs API keys; does **not** replace normal `.\dev.ps1` use):

```powershell
cd backend
$env:PYTHONUNBUFFERED='1'
uv run python scripts\week4_evaluate.py --mode live --label baseline --out ..\docs\week4\week4_eval_results.csv
uv run python scripts\week4_evaluate.py --mode live --label improved --out ..\docs\week4\week4_eval_results.csv
```

Write-up: [docs/WEEK4_EVAL.md](docs/WEEK4_EVAL.md) · [docs/WEEK4_PROJECT_REPORT.docx](docs/WEEK4_PROJECT_REPORT.docx) · Loom script: [docs/WEEK4_DEMO_SCRIPTS.docx](docs/WEEK4_DEMO_SCRIPTS.docx)

Regenerate Word docs (optional):

```powershell
cd backend
uv run python scripts\build_project_report_docx.py
uv run python scripts\build_week4_docs.py
```

---

## Safety

Agents may file, classify, investigate, and draft reports. They must **never** approve, deny, settle, or pay claims. Final decisions remain with a licensed human adjuster.
