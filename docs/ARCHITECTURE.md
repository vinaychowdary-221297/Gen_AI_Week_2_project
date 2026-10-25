# Architecture — Insurance Claims Intelligence (Week 3)

System design for the local **single-agent claim process** built on Week 2 Hybrid RAG.  
Product overview and setup: [README.md](../README.md). Week 3 process notes: [WEEK3_AGENTIC.md](WEEK3_AGENTIC.md).

---

## 1. Design goals

| Goal | Approach |
| --- | --- |
| Agentic claim lifecycle | One LangGraph agent moves Filing → Classification → Investigation → Report → Human Review |
| Grounded answers | Deterministic tools for structured facts; Hybrid RAG only for policy language |
| Live observability | SSE event bus → Adjuster Desk stages + Live Workflow canvas |
| Human safety | Never approve / deny / settle / pay; always `human_review_required` |
| External context | Keenable for weather + illustrative market parts/labor (not settlement math) |
| Correct money math | Estimate totals / deltas / illustrative net computed in **code** (Decimal), not LLM prose |

**Explicit non-goal:** multi-agent teams. Week 3 is **single-agent, multi-tool, multi-stage**.

---

## 2. High-level system

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)                                         │
│  ┌──────────────────┐  ┌──────────────────┐  shared             │
│  │ Adjuster Desk /  │  │ Live Workflow    │  InvestigationProvider│
│  │ ask + report     │  │ debug canvas     │  (one live run)      │
│  └────────┬─────────┘  └────────┬─────────┘                     │
└───────────┼─────────────────────┼───────────────────────────────┘
            │ REST + SSE          │
            ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI                                                         │
│  /api/investigate  → start run                                   │
│  /api/runs/{id}/events → SSE (EventSource)                       │
│  /api/health, claims, docs, evaluation                           │
│  Event bus (in-memory) ←── LangGraph nodes emit progress         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  LangGraph agent (Nebius chat + tool calling)                    │
│                                                                  │
│     ┌────────┐   tool_calls   ┌────────┐                         │
│     │ agent  │───────────────►│ tools  │──┐                      │
│     └───▲────┘                └────────┘  │                      │
│         │     no tools / done              │ results              │
│         │◄─────────────────────────────────┘                      │
│         │                                                        │
│         ├── force_report ──► agent (nudge final report tool)     │
│         └── human_handoff ──► END                                │
└───────────────────────────────┬─────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ Local data    │    │ Hybrid RAG       │    │ Keenable         │
│ claims/       │    │ BM25 + Nebius    │    │ search_web       │
│ policies/     │    │ embed + Pinecone │    │ market research  │
│ estimate MD   │    │ + RRF            │    │                  │
└───────────────┘    └──────────────────┘    └──────────────────┘
```

---

## 3. Frontend architecture

| Route | Component | Role |
| --- | --- | --- |
| `/`, `/adjuster` | `AdjusterPage` | Human-facing desk: claim, question, Run, stage strip, report review |
| `/workflow` | `Dashboard` | Debug-only canvas; mirrors the same run (no separate Run) |
| `/claims`, `/documents`, `/evaluation` | Browse / eval helpers | Supporting views |

### Shared investigation state

`InvestigationProvider` (`frontend/src/hooks/useInvestigation.ts`) owns:

- `running`, `runId`, `nodeState`, `logs`, `report`, `currentStage`, `handoff`
- Active / traversed edge IDs for the canvas
- SSE subscription to `/api/runs/{runId}/events`

Both Adjuster Desk and Live Workflow consume this context so starting a run on the desk continues on the workflow tab.

### Live Workflow

- React Flow graph (`WorkflowCanvas`) with icon nodes mapped from tool/event `node_id`s
- Click node → side panel with **Input / Output / Logs** only
- Minimal chrome (debug view)

---

## 4. Backend architecture

```
backend/app/
  main.py              # FastAPI app
  config.py            # Settings from .env
  api/routes.py        # HTTP + SSE endpoints
  events/bus.py        # In-memory run event bus
  agent/
    graph.py           # LangGraph: agent ↔ tools ↔ force_report ↔ handoff
    prompts.py         # System + stage guidance
    tools.py           # Week 2 tools + report builder
    week3_tools.py     # Classify, estimates, Keenable, handoff
    estimate_docs.py   # Parse / compare preliminary vs facility Markdown
  clients/
    nebius.py          # Chat + embeddings
    pinecone_client.py # Dense vector store
    keenable.py        # Web search API
  rag/
    hybrid.py          # BM25 + dense + RRF
    bm25_store.py
    chunking.py
    rrf.py
  data/
    loader.py          # Cached JSON loaders
    models.py          # Pydantic claim / report shapes
```

### Investigate flow

1. Client `POST /api/investigate` with `{ claim_id, question }`.
2. API creates `run_id`, starts `run_investigation`.
3. Graph emits SSE events (`node_started`, `tool_called`, `stage_changed`, `report_generated`, …).
4. Client EventSource updates UI; final report attached to the run.

### Process vs narrow mode

`run_investigation` inspects the question:

- **Process / comprehensive** — full stage order + required `search_web` (weather) + `research_market_repair_costs`.
- **Narrow** — only tools needed for the question.
- **Portfolio** — no claim; `query_portfolio_data` then report with `claim_id=portfolio`.

---

## 5. LangGraph control flow

```
                    ┌──────────────┐
                    │    START     │
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
           ┌───────►│    agent     │◄──────────────┐
           │        │ (Nebius LLM) │               │
           │        └──────┬───────┘               │
           │               │                       │
           │     ┌─────────┼─────────┐             │
           │     ▼         ▼         ▼             │
           │  tools    force_report  handoff       │
           │     │         │         │             │
           │     │         └────► agent            │
           │     │                   END ◄── handoff
           │     ├── report? ──► END
           │     └── else ─────► agent
           └─────────────────────┘
```

| Node | Responsibility |
| --- | --- |
| `agent` | Nebius chat with tool schemas; emits LLM/agent canvas events |
| `tools` | Execute tool calls; map each tool → canvas `node_id`; update stage / failures |
| `force_report` | If the model stops without a report, nudge once to call `generate_investigation_report` |
| `human_handoff` | Terminal partial report + `awaiting_human` |

Bounds: `MAX_TOOL_CALLS`, LangGraph `recursion_limit` (raised for comprehensive runs), tool retry for network failures, consecutive-failure → handoff.

---

## 6. Tools map

### Structured / local (no LLM math)

| Tool | Canvas node (typical) | Data |
| --- | --- | --- |
| `get_claim_details` | claim_lookup | `claims.json` |
| `validate_policy_dates` | coverage_check | policy dates |
| `check_coverage_facts` | coverage_check | listed coverages / deductibles |
| `analyze_repair_estimate` | estimate_analysis | line items + facility MD (Decimal) |
| `check_missing_documents` | missing_docs | checklist |
| `find_similar_claims` | similar_claims | claims JSON |
| `query_portfolio_data` | portfolio | full book |
| `classify_claim` | classify | scenario / severity |
| `list_claim_documents` | documents | claim folder + FNOL list |
| `parse_repair_estimate_document` | estimate_parse | Markdown |
| `build_preliminary_estimate` | preliminary_estimate | desk estimate |
| `compare_estimate_versions` | estimate_compare | prelim vs facility |
| `generate_investigation_report` | report | **overwrites $ from code** |

### Retrieval

| Tool | Path |
| --- | --- |
| `search_policy_documents` | BM25 (local) ∥ Nebius embed → Pinecone → RRF fuse |

### External web (Keenable)

| Tool | Purpose |
| --- | --- |
| `search_web` | Weather / public facts; cite URLs |
| `research_market_repair_costs` | Per-line parts + local labor rate queries |
| `build_illustrative_market_estimate` | Shop total + market research side-by-side |

### Handoff

| Tool | Purpose |
| --- | --- |
| `request_human_handoff` | Escalate when blocked or tools fail repeatedly |

---

## 7. Hybrid RAG (Week 2 core)

```
Policy Markdown ──chunk──► BM25 index (local)
                    └──embed (Nebius)──► Pinecone namespace

Query ──► BM25 top-k ──┐
        └► Dense top-k ─┴──► Reciprocal Rank Fusion ──► citations
```

- Filtered by `policy_id` when claim-scoped.
- Used when the question needs **policy document language**, not for portfolio counts or raw estimate arithmetic.

---

## 8. Estimate & financials model

```
                    ┌─────────────────────────┐
                    │ Preliminary_Estimate.md │  desk / info on file
                    └───────────┬─────────────┘
                                │ compare_estimate_versions
                    ┌───────────▼─────────────┐
                    │ Repair_Facility_Estimate│  shop / tear-down
                    └───────────┬─────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
 estimate_analysis      illustrative_financials    market_research
 (lines, deltas,        (facility − deductible     (Keenable context
  duplicates)            illustrative net)           URLs / ranges)
        │                       │
        └───────────┬───────────┘
                    ▼
        generate_investigation_report
        (code verifies $; scrubs invented deltas from summary)
```

| Field | Source of truth |
| --- | --- |
| Facility / submitted totals | Line items + Markdown grand total (synced `estimate_total`) |
| Illustrative net | Code: facility − applicable deductible |
| Market research | Keenable — **does not** set illustrative net |

---

## 9. Event & stage model

Events flow: tool/graph code → `event_bus.emit` → SSE → frontend `applyEvent`.

Important event types:

- `workflow_started` / `workflow_completed` / `workflow_failed`
- `node_started` / `node_completed` / `node_failed`
- `tool_called` / `tool_result` / `tool_retry`
- `retrieval_started` / `retrieval_completed`
- `stage_changed`
- `report_generated` / `handoff_requested`
- `heartbeat`

Logical stages (UI pipeline): `filing` → `classification` → `investigation` → `report` → `human_review`.

---

## 10. Data layout

```
backend/data/
  policies.json + policies/*.md
  claims.json
  claim_documents.json
  repair_line_items.json|.csv
  required_documents.json
  evaluation_questions.json
  claims/{CLM-xxxx}/
    FNOL.md
    Preliminary_Estimate.md
    Repair_Facility_Estimate.md
  indexes/          # BM25
```

Generation: `scripts/generate_data.py` (keeps `estimate_total` aligned with facility line sums).  
Ingest: `scripts/ingest_docs.py` (BM25 + Pinecone).

---

## 11. External dependencies

| Service | Role |
| --- | --- |
| **Nebius Token Factory** | Chat (tool calling) + embeddings |
| **Pinecone** | Dense policy vectors |
| **Keenable** | Web search for weather + market research |

All claim/policy business data and BM25 stay local. Secrets only in `backend/.env` (gitignored).

---

## 12. Safety boundaries

```
Allowed                         Not allowed
────────────────────────────    ────────────────────────────
File / classify / investigate   Approve or deny claim
Draft report + citations        Settle or pay
Flag duplicates / missing docs  Invent weather or market $
Hand off to human               Treat illustrative net as payment
```

Reports always set `human_review_required=true`. UI copy states the desk never settles or pays.

---

## 13. Related docs

| Doc | Contents |
| --- | --- |
| [README.md](../README.md) | Week 3 product README, setup, demo |
| [WEEK3_AGENTIC.md](WEEK3_AGENTIC.md) | Stages, tools, Keenable, demo script |
| [SETUP_WINDOWS.md](../SETUP_WINDOWS.md) | Windows install & troubleshooting |
| [PROJECT_REPORT.docx](PROJECT_REPORT.docx) | Narrative report / learnings |
