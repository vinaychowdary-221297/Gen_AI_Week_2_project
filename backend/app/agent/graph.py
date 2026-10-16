"""LangGraph tool-calling investigation agent with live event emission."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agent.prompts import SYSTEM_PROMPT
# Import tools module (not bound names) so uvicorn --reload always picks up
# the latest execute_tool / schemas without a stale graph closure.
from app.agent import tools as agent_tools
from app.clients.nebius import NebiusConfigurationError, get_nebius
from app.config import get_settings
from app.events.bus import event_bus


class AgentState(TypedDict, total=False):
    run_id: str
    claim_id: str
    question: str
    messages: List[Dict[str, Any]]
    tool_call_count: int
    report: Optional[Dict[str, Any]]
    status: str
    error: Optional[str]


def _assistant_message_to_dict(message: Any) -> Dict[str, Any]:
    tool_calls = []
    raw_calls = getattr(message, "tool_calls", None) or []
    for tc in raw_calls:
        # OpenAI SDK objects or dicts
        if isinstance(tc, dict):
            tool_calls.append(tc)
        else:
            fn = getattr(tc, "function", None)
            tool_calls.append(
                {
                    "id": getattr(tc, "id", None),
                    "type": "function",
                    "function": {
                        "name": getattr(fn, "name", None),
                        "arguments": getattr(fn, "arguments", "{}"),
                    },
                }
            )
    return {
        "role": "assistant",
        "content": getattr(message, "content", None),
        "tool_calls": tool_calls or None,
    }


def agent_node(state: AgentState) -> AgentState:
    run_id = state["run_id"]
    settings = get_settings()
    event_bus.emit(
        run_id,
        "node_started",
        status="running",
        node_id="langgraph_agent",
        input_summary={"tool_call_count": state.get("tool_call_count", 0)},
    )
    event_bus.emit(
        run_id,
        "node_started",
        status="running",
        node_id="nebius_llm",
        input_summary={"model": settings.nebius_chat_model},
    )

    started = time.perf_counter()
    nebius = get_nebius()
    response = nebius.chat(
        messages=state["messages"],
        tools=agent_tools.TOOL_SCHEMAS,
        tool_choice="auto",
        temperature=0.1,
        max_tokens=2500,
    )
    duration = (time.perf_counter() - started) * 1000
    message = response.choices[0].message
    as_dict = _assistant_message_to_dict(message)
    messages = list(state["messages"]) + [as_dict]

    event_bus.emit(
        run_id,
        "node_completed",
        status="completed",
        node_id="nebius_llm",
        duration_ms=duration,
        output_summary={
            "has_tool_calls": bool(as_dict.get("tool_calls")),
            "tool_names": [
                (tc.get("function") or {}).get("name")
                for tc in (as_dict.get("tool_calls") or [])
            ],
            "content_preview": (as_dict.get("content") or "")[:240],
        },
    )
    event_bus.emit(
        run_id,
        "node_completed",
        status="completed",
        node_id="langgraph_agent",
        duration_ms=duration,
        output_summary={"tool_calls": len(as_dict.get("tool_calls") or [])},
    )

    return {
        **state,
        "messages": messages,
        "status": "reasoning",
    }


def tools_node(state: AgentState) -> AgentState:
    run_id = state["run_id"]
    messages = list(state["messages"])
    last = messages[-1]
    tool_calls = last.get("tool_calls") or []
    count = state.get("tool_call_count", 0)
    report = state.get("report")

    for tc in tool_calls:
        count += 1
        fn = tc.get("function") or {}
        name = fn.get("name")
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
        except json.JSONDecodeError:
            args = {}

        node_id = agent_tools.TOOL_NODE_MAP.get(name, name)
        event_bus.emit(
            run_id,
            "tool_called",
            status="running",
            node_id=node_id,
            input_summary={"tool": name, "arguments": args},
            tool_name=name,
        )
        event_bus.emit(
            run_id,
            "node_started",
            status="running",
            node_id=node_id,
            input_summary=args,
        )
        # Claim intake visual cue on first claim lookup
        if name == "get_claim_details":
            event_bus.emit(
                run_id,
                "node_started",
                status="running",
                node_id="claim_intake",
                input_summary=args,
            )
            event_bus.emit(
                run_id,
                "node_started",
                status="running",
                node_id="claim_database",
                input_summary=args,
            )

        started = time.perf_counter()
        try:
            result = agent_tools.execute_tool(name, args, run_id=run_id)
            duration = (time.perf_counter() - started) * 1000
            payload = agent_tools.tool_result_json(result)
            event_bus.emit(
                run_id,
                "tool_result",
                status="completed",
                node_id=node_id,
                duration_ms=duration,
                output_summary=result if isinstance(result, dict) else {"result": result},
                tool_name=name,
            )
            event_bus.emit(
                run_id,
                "node_completed",
                status="completed",
                node_id=node_id,
                duration_ms=duration,
                output_summary=_compact(result),
            )
            if name == "get_claim_details":
                event_bus.emit(
                    run_id,
                    "node_completed",
                    status="completed",
                    node_id="claim_intake",
                    duration_ms=duration,
                    output_summary=_compact(result),
                )
                event_bus.emit(
                    run_id,
                    "node_completed",
                    status="completed",
                    node_id="claim_database",
                    duration_ms=duration,
                    output_summary={"source": "local JSON"},
                )
            if name == "generate_investigation_report":
                report = _ensure_report_citations(result, messages)
                event_bus.emit(
                    run_id,
                    "report_generated",
                    status="completed",
                    node_id="report_generator",
                    output_summary=_compact(report),
                )
                event_bus.emit(
                    run_id,
                    "node_started",
                    status="running",
                    node_id="human_review",
                    input_summary={"human_review_required": True},
                )
                event_bus.emit(
                    run_id,
                    "node_completed",
                    status="completed",
                    node_id="human_review",
                    output_summary={"awaiting_adjuster": True},
                )
        except Exception as exc:  # noqa: BLE001
            duration = (time.perf_counter() - started) * 1000
            payload = json.dumps({"error": str(exc)})
            event_bus.emit(
                run_id,
                "node_failed",
                status="failed",
                node_id=node_id,
                duration_ms=duration,
                error=str(exc),
                tool_name=name,
            )
            result = {"error": str(exc)}

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "name": name,
                "content": payload,
            }
        )

    return {
        **state,
        "messages": messages,
        "tool_call_count": count,
        "report": report,
        "status": "tools_executed",
    }


def should_continue(state: AgentState) -> str:
    settings = get_settings()
    if state.get("report"):
        return "end"
    if state.get("tool_call_count", 0) >= settings.max_tool_calls:
        return "end"
    last = (state.get("messages") or [])[-1]
    if last.get("role") == "assistant" and last.get("tool_calls"):
        return "tools"
    # Assistant finished without report — force a final nudge once
    if last.get("role") == "assistant" and not state.get("report"):
        return "force_report"
    return "end"


def force_report_node(state: AgentState) -> AgentState:
    """Nudge the model to emit generate_investigation_report if it stopped early."""
    messages = list(state["messages"])
    messages.append(
        {
            "role": "user",
            "content": (
                "You must now call generate_investigation_report with the best available "
                "evidence gathered so far. "
                f"claim_summary must directly answer this Question: {state.get('question', '')}. "
                "Keep it to 1–3 sentences with the conclusion and key dates/facts — "
                "not a full FNOL narrative unless asked. "
                "Do not approve or deny the claim. Mark human_review_required=true."
            ),
        }
    )
    return {**state, "messages": messages, "status": "force_report"}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("force_report", force_report_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "force_report": "force_report",
            "end": END,
        },
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("force_report", "agent")
    return graph.compile()


_compiled = None


def get_graph():
    """Rebuild graph each process start; avoid stale compiled graph across reloads."""
    global _compiled
    # Always rebuild — cheap for this MVP and prevents stale tool bindings
    _compiled = build_graph()
    return _compiled


def _compact(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in list(value.items())[:25]:
            if k in {"repair_line_items", "bm25_results", "pinecone_results", "document_records"}:
                out[k] = f"[{len(v)} items]" if isinstance(v, list) else v
            elif isinstance(v, list) and len(v) > 8:
                out[k] = v[:8] + ["…"]
            elif isinstance(v, str) and len(v) > 400:
                out[k] = v[:400] + "…"
            else:
                out[k] = v
        return out
    return value


def _citations_from_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pull citations from the latest search_policy_documents tool result."""
    from app.data.models import coerce_citation_dict

    for msg in reversed(messages):
        if msg.get("role") != "tool" or msg.get("name") != "search_policy_documents":
            continue
        try:
            payload = json.loads(msg.get("content") or "{}")
        except json.JSONDecodeError:
            continue
        citations = payload.get("citations") or []
        if isinstance(citations, list) and citations:
            return [coerce_citation_dict(c) for c in citations if c]
    return []


def _date_citations_from_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build a Declarations-style citation from validate_policy_dates if RAG was skipped."""
    for msg in reversed(messages):
        if msg.get("role") != "tool" or msg.get("name") != "validate_policy_dates":
            continue
        try:
            payload = json.loads(msg.get("content") or "{}")
        except json.JSONDecodeError:
            continue
        policy_id = payload.get("policy_id") or "policy"
        loss = payload.get("loss_date")
        eff = payload.get("effective_date")
        exp = payload.get("expiration_date")
        within = payload.get("loss_date_within_period")
        if not (loss and eff and exp):
            continue
        verdict = "within" if within else "outside"
        return [
            {
                "document_name": f"{policy_id}.md",
                "section": "Declarations — Period of coverage",
                "page_number": None,
                "excerpt": (
                    f"Effective Date: {eff}. Expiration Date: {exp}. "
                    f"Loss date {loss} is {verdict} the policy period "
                    f"(tool: validate_policy_dates)."
                ),
                "chunk_id": None,
                "score": None,
            }
        ]
    return []


def _portfolio_citations_from_messages(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    for msg in reversed(messages):
        if msg.get("role") != "tool" or msg.get("name") != "query_portfolio_data":
            continue
        try:
            payload = json.loads(msg.get("content") or "{}")
        except json.JSONDecodeError:
            continue
        note = payload.get("note") or ""
        active = payload.get("active_policy_ids") or []
        excerpt = note or (
            f"active_policy_count={payload.get('active_policy_count')}; "
            f"ids={active}; by_status={payload.get('policies_by_status')}"
        )
        return [
            {
                "document_name": "policies.json",
                "section": "Synthetic policy book",
                "page_number": None,
                "excerpt": str(excerpt)[:500],
                "chunk_id": None,
                "score": None,
            }
        ]
    return []


def _ensure_report_citations(
    report: Optional[Dict[str, Any]], messages: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """If the model omitted evidence, backfill from Hybrid RAG, date, or portfolio tools."""
    if not isinstance(report, dict):
        return report
    if report.get("retrieved_evidence"):
        return report
    filled = (
        _citations_from_messages(messages)
        or _date_citations_from_messages(messages)
        or _portfolio_citations_from_messages(messages)
    )
    if filled:
        return {**report, "retrieved_evidence": filled}
    return report


def run_investigation(run_id: str, claim_id: str, question: str) -> Dict[str, Any]:
    """Execute the LangGraph agent and stream events via the bus."""
    settings = get_settings()
    event_bus.update_run(run_id, status="running")

    # Fail fast with a clear config error if the chat model rejects tools
    try:
        get_nebius().validate_tool_calling()
    except NebiusConfigurationError as exc:
        event_bus.emit(
            run_id,
            "workflow_failed",
            status="failed",
            error=str(exc),
            node_id="nebius_llm",
        )
        event_bus.update_run(run_id, status="failed", error=str(exc))
        raise

    event_bus.emit(
        run_id,
        "workflow_started",
        status="running",
        node_id="start_trigger",
        input_summary={"claim_id": claim_id, "question": question},
    )
    event_bus.emit(
        run_id,
        "node_started",
        status="running",
        node_id="start_trigger",
    )
    event_bus.emit(
        run_id,
        "node_completed",
        status="completed",
        node_id="start_trigger",
    )

    portfolio_mode = (not claim_id) or str(claim_id).lower() in {
        "portfolio",
        "none",
        "n/a",
    }
    if portfolio_mode:
        user_content = (
            "Claim ID: none (portfolio / dataset question — no single claim selected)\n"
            f"Question: {question}\n\n"
            "Use query_portfolio_data to answer from the full policies/claims dataset. "
            "Do not assume a single claim's policy. Finish with generate_investigation_report "
            "using claim_id='portfolio'. Put the direct answer (counts and IDs) in claim_summary."
        )
    else:
        user_content = (
            f"Claim ID: {claim_id}\n"
            f"Question: {question}\n\n"
            "Answer this Question only. Call only the tools required for it, then finish with "
            "generate_investigation_report. Put the direct answer (with key dates/facts) in "
            "claim_summary — do not write a full accident narrative unless the Question asks for one."
        )
    initial: AgentState = {
        "run_id": run_id,
        "claim_id": claim_id,
        "question": question,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "tool_call_count": 0,
        "report": None,
        "status": "started",
        "error": None,
    }

    graph = get_graph()
    try:
        # LangGraph invoke with recursion / step bound
        final_state = graph.invoke(
            initial,
            config={"recursion_limit": settings.max_tool_calls * 3 + 5},
        )
        report = final_state.get("report")
        if not report:
            # Deterministic fallback report from last tool messages if model skipped
            report = {
                "claim_id": claim_id,
                "investigation_status": "pending_human_review",
                "claim_summary": f"Investigation incomplete for {claim_id}; model did not emit final report tool.",
                "policy_facts": {},
                "retrieved_evidence": [],
                "coverage_considerations": [],
                "estimate_analysis": {},
                "potential_discrepancies": [],
                "missing_documents": [],
                "illustrative_financials": {},
                "recommended_next_steps": [
                    "Re-run investigation or manually call tools from the API.",
                    "Human review required.",
                ],
                "unresolved_questions": [
                    "Final generate_investigation_report tool was not called by the model."
                ],
                "human_review_required": True,
                "disclaimer": (
                    "This report is an investigative aid only. Final decisions require human review."
                ),
            }
            event_bus.emit(
                run_id,
                "report_generated",
                status="completed",
                node_id="report_generator",
                output_summary=report,
            )

        event_bus.emit(
            run_id,
            "workflow_completed",
            status="completed",
            node_id="human_review",
            output_summary={"claim_id": claim_id, "awaiting_human_review": True},
        )
        event_bus.update_run(run_id, status="completed", report=report)
        return {"run_id": run_id, "status": "completed", "report": report}
    except Exception as exc:  # noqa: BLE001
        event_bus.emit(
            run_id,
            "workflow_failed",
            status="failed",
            error=str(exc),
        )
        event_bus.update_run(run_id, status="failed", error=str(exc))
        raise
