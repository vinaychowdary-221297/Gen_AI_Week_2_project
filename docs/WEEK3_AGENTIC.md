# Week 3 — Agentic claim process (single agent)

Companion to the main [README.md](../README.md). Full system diagrams: [ARCHITECTURE.md](ARCHITECTURE.md). Week 3 extends Week 2 Hybrid RAG into a **single-agent, multi-stage claim process**.

## Goals

| Pillar | How it shows up |
| --- | --- |
| Control flow | Filing → Classification → Investigation → Report → Human Review |
| State | Shared run: stage, step log, failures, handoff, report |
| Tool failure | Retry once for network tools (Keenable / RAG); escalate after consecutive failures |
| Human boundary | `request_human_handoff` + always `human_review_required`; never pay/settle |
| External facts | Keenable web search (weather) + market parts/labor research |
| Estimates | Preliminary (desk) vs facility (shop) + compare |

**Architecture choice:** one LangGraph agent with an expanded tool set — **not** multi-agent.

## New tools

`classify_claim`, `list_claim_documents`, `parse_repair_estimate_document`, `build_preliminary_estimate`, `compare_estimate_versions`, `search_web`, `research_market_repair_costs`, `build_illustrative_market_estimate`, `request_human_handoff`.

## Estimates & money

- **Preliminary** — information on file; may change after the vehicle is at a facility.  
- **Facility** — shop Markdown under `backend/data/claims/{id}/Repair_Facility_Estimate.md`.  
- **Illustrative financials** — facility/submitted + deductible + illustrative net, computed in **code** (Decimal).  
- **Market research** — Keenable public price **context** only; does not set the illustrative net.  
- Report builder overwrites estimate `$` from tools so the LLM cannot invent deltas.

## Keenable setup

1. Create a key at [keenable.ai](https://keenable.ai/) (`keen_…`).  
2. In `backend/.env`:

```env
KEENABLE_API_KEY=keen_your_real_key_here
KEENABLE_MAX_RESULTS=5
KEENABLE_SEARCH_MODE=pro
KEENABLE_MARKET_LINE_LIMIT=5
MAX_TOOL_CALLS=28
AGENT_TIMEOUT_SECONDS=300
```

3. Regenerate estimate files if needed: `uv run python scripts\generate_data.py`  
4. Run: `.\dev.ps1` from repo root.

## UI

| Route | Role |
| --- | --- |
| `/` Adjuster Desk | Ask question → Run → review draft report |
| `/workflow` Live Workflow | Shared live run for debugging; click node → input / output / logs |

## Demo script

1. **CLM-1001** — comprehensive full claim process → stages on Adjuster Desk + Live Workflow → prelim vs facility → human review.  
2. **CLM-1013** — vandalism / comprehensive; confirm estimate totals match (no invented deltas).  
3. **CLM-1004** — ask for weather at loss → `search_web`.  
4. **CLM-1005** — duplicate ADAS lines via estimate analyze/parse.  
5. **CLM-1003** — expired policy → classification / human path.  
6. Bad/missing Keenable key → retry; do not invent weather or market prices.

## Safety

Agents may file, classify, investigate, and draft reports. They must **never** approve, deny, settle, or pay claims. Final decisions remain with a licensed human adjuster.
