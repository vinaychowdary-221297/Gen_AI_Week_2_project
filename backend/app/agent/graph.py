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
    stage: str
    consecutive_tool_failures: int
    failed_tools: List[str]
    handoff: Optional[Dict[str, Any]]
    step_log: List[Dict[str, Any]]
    process_mode: bool


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
    consecutive_failures = int(state.get("consecutive_tool_failures") or 0)
    failed_tools = list(state.get("failed_tools") or [])
    step_log = list(state.get("step_log") or [])
    handoff = state.get("handoff")
    stage = state.get("stage") or "investigation"
    settings = get_settings()

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
        # Stage cues from tool names
        if name in {"get_claim_details", "list_claim_documents"}:
            stage = "filing"
        elif name == "classify_claim":
            stage = "classification"
        elif name == "generate_investigation_report":
            stage = "report"
        elif name == "request_human_handoff":
            stage = "human_review"
        else:
            stage = "investigation"

        event_bus.emit(
            run_id,
            "stage_changed",
            status="running",
            node_id=f"stage_{stage}",
            input_summary={"stage": stage, "tool": name},
        )
        event_bus.emit(
            run_id,
            "tool_called",
            status="running",
            node_id=node_id,
            input_summary={"tool": name, "arguments": args, "stage": stage},
            tool_name=name,
        )
        event_bus.emit(
            run_id,
            "node_started",
            status="running",
            node_id=node_id,
            input_summary=args,
        )
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
        result: Any = None
        retry_attempted = False
        try:
            result = agent_tools.execute_tool(name, args, run_id=run_id)
        except Exception as first_exc:  # noqa: BLE001
            if name in getattr(agent_tools, "RETRYABLE_TOOLS", set()):
                retry_attempted = True
                event_bus.emit(
                    run_id,
                    "tool_retry",
                    status="running",
                    node_id="tool_retry",
                    error=str(first_exc),
                    tool_name=name,
                    input_summary={"attempt": 2},
                )
                try:
                    result = agent_tools.execute_tool(name, args, run_id=run_id)
                except Exception as second_exc:  # noqa: BLE001
                    result = {
                        "error": str(second_exc),
                        "retry_attempted": True,
                        "recoverable": True,
                    }
            else:
                result = {
                    "error": str(first_exc),
                    "retry_attempted": False,
                    "recoverable": True,
                }

        duration = (time.perf_counter() - started) * 1000
        is_error = isinstance(result, dict) and result.get("error")
        if is_error:
            consecutive_failures += 1
            failed_tools.append(str(name))
            payload = agent_tools.tool_result_json(result)
            event_bus.emit(
                run_id,
                "node_failed",
                status="failed",
                node_id=node_id,
                duration_ms=duration,
                error=str(result.get("error")),
                tool_name=name,
                output_summary={"retry_attempted": retry_attempted},
            )
            step_log.append({"tool": name, "status": "failed", "stage": stage})
        else:
            consecutive_failures = 0
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
            step_log.append({"tool": name, "status": "ok", "stage": stage})
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
                stage = "human_review"
            if name == "request_human_handoff" and isinstance(result, dict):
                handoff = result
                stage = "human_review"
                event_bus.emit(
                    run_id,
                    "handoff_requested",
                    status="awaiting_human",
                    node_id="human_handoff",
                    output_summary=_compact(result),
                )

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "name": name,
                "content": payload,
            }
        )

        if consecutive_failures >= settings.max_consecutive_tool_failures and not handoff:
            handoff = {
                "handoff_requested": True,
                "reason": (
                    f"Auto-escalated after {consecutive_failures} consecutive tool failures: "
                    f"{failed_tools[-3:]}"
                ),
                "blocking_questions": [
                    "Retry external tools or continue investigation manually."
                ],
                "from_stage": stage,
                "status": "awaiting_human",
                "human_review_required": True,
            }
            event_bus.emit(
                run_id,
                "handoff_requested",
                status="awaiting_human",
                node_id="human_handoff",
                output_summary=handoff,
            )

    return {
        **state,
        "messages": messages,
        "tool_call_count": count,
        "report": report,
        "status": "tools_executed",
        "stage": stage,
        "consecutive_tool_failures": consecutive_failures,
        "failed_tools": failed_tools,
        "step_log": step_log,
        "handoff": handoff,
    }


def should_continue(state: AgentState) -> str:
    settings = get_settings()
    if state.get("handoff") and state.get("handoff", {}).get("handoff_requested"):
        return "human_handoff"
    if state.get("report"):
        return "end"
    if state.get("tool_call_count", 0) >= settings.max_tool_calls:
        if not state.get("report"):
            return "force_report"
        return "end"
    last = (state.get("messages") or [])[-1]
    if last.get("role") == "assistant" and last.get("tool_calls"):
        return "tools"
    # Assistant finished without report — force a final nudge once
    if last.get("role") == "assistant" and not state.get("report"):
        return "force_report"
    return "end"


def human_handoff_node(state: AgentState) -> AgentState:
    """Terminal handoff: partial report + awaiting_human status."""
    run_id = state["run_id"]
    handoff = state.get("handoff") or {}
    claim_id = state.get("claim_id") or "unknown"
    report = state.get("report") or {
        "claim_id": claim_id,
        "investigation_status": "awaiting_human",
        "claim_summary": (
            f"Processing paused for human review: {handoff.get('reason', 'handoff requested')}."
        ),
        "policy_facts": {"handoff": handoff},
        "retrieved_evidence": [],
        "coverage_considerations": [],
        "estimate_analysis": {},
        "potential_discrepancies": [],
        "missing_documents": [],
        "illustrative_financials": {},
        "recommended_next_steps": [
            "Licensed adjuster should resume from handoff reason and blocking questions.",
        ],
        "unresolved_questions": list(handoff.get("blocking_questions") or [])
        or [str(handoff.get("reason") or "Human review required")],
        "human_review_required": True,
        "disclaimer": (
            "Autonomous agent stopped. No approval, denial, settlement, or payment was made."
        ),
    }
    event_bus.emit(
        run_id,
        "node_completed",
        status="awaiting_human",
        node_id="human_handoff",
        output_summary=_compact(handoff),
    )
    event_bus.emit(
        run_id,
        "node_completed",
        status="awaiting_human",
        node_id="human_review",
        output_summary={"awaiting_adjuster": True, "handoff": True},
    )
    event_bus.emit(
        run_id,
        "report_generated",
        status="awaiting_human",
        node_id="report_generator",
        output_summary=_compact(report),
    )
    event_bus.emit(
        run_id,
        "workflow_completed",
        status="awaiting_human",
        node_id="human_review",
        output_summary={"awaiting_human": True, "handoff": True},
    )
    event_bus.update_run(run_id, status="awaiting_human", report=report)
    return {
        **state,
        "report": report,
        "stage": "human_review",
        "status": "awaiting_human",
    }


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
    graph.add_node("human_handoff", human_handoff_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "force_report": "force_report",
            "human_handoff": "human_handoff",
            "end": END,
        },
    )

    def after_tools(state: AgentState) -> str:
        if state.get("handoff") and state.get("handoff", {}).get("handoff_requested"):
            return "human_handoff"
        if state.get("report"):
            return "end"
        return "agent"

    graph.add_conditional_edges(
        "tools",
        after_tools,
        {
            "agent": "agent",
            "human_handoff": "human_handoff",
            "end": END,
        },
    )
    graph.add_edge("force_report", "agent")
    graph.add_edge("human_handoff", END)
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
    from app.data.loader import clear_data_caches

    clear_data_caches()  # pick up synced estimate_total / line items
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
    q_lower = (question or "").lower()
    process_mode = (not portfolio_mode) and (
        "full claim process" in q_lower
        or "run full" in q_lower
        or "end-to-end" in q_lower
        or "claim process" in q_lower
        or "comprehensive" in q_lower
        or "complete investigation" in q_lower
    )
    if portfolio_mode:
        user_content = (
            "Claim ID: none (portfolio / dataset question — no single claim selected)\n"
            f"Question: {question}\n\n"
            "Use query_portfolio_data to answer from the full policies/claims dataset. "
            "Do not assume a single claim's policy. Finish with generate_investigation_report "
            "using claim_id='portfolio'. Put the direct answer (counts and IDs) in claim_summary."
        )
    elif process_mode:
        user_content = (
            f"Claim ID: {claim_id}\n"
            f"Question: {question}\n\n"
            "Run the FULL / comprehensive claim process in order:\n"
            "1) Filing: get_claim_details + list_claim_documents\n"
            "2) Classification: classify_claim\n"
            "3) Investigation: validate dates/coverage as needed; "
            "build_preliminary_estimate; parse_repair_estimate_document(facility); "
            "analyze_repair_estimate; compare_estimate_versions; "
            "REQUIRED search_web for weather at the claim location on/near the accident date "
            "and any other required public facts (road conditions, recalls, etc.); "
            "REQUIRED research_market_repair_costs (Keenable); policy RAG if needed\n"
            "4) generate_investigation_report with human_review_required=true\n"
            "Do not skip search_web on this comprehensive run. Cite URLs; if search fails, "
            "record the failure — never invent weather or market prices. "
            "If tools fail repeatedly, call request_human_handoff. "
            "Never approve, deny, settle, or pay. "
            "Note that preliminary estimates may change after the vehicle is at a repair facility."
        )
    else:
        user_content = (
            f"Claim ID: {claim_id}\n"
            f"Question: {question}\n\n"
            "Answer this Question only. Call only the tools required for it, then finish with "
            "generate_investigation_report. Put the direct answer (with key dates/facts) in "
            "claim_summary — do not write a full accident narrative unless the Question asks for one. "
            "Use classify_claim / estimate / search_web tools when the question needs them."
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
        "stage": "filing" if not portfolio_mode else "investigation",
        "consecutive_tool_failures": 0,
        "failed_tools": [],
        "handoff": None,
        "step_log": [],
        "process_mode": process_mode,
    }

    graph = get_graph()
    try:
        # LangGraph counts each agent/tools hop. Comprehensive runs call many tools
        # (often one-at-a-time), so keep a generous ceiling above max_tool_calls.
        recursion_limit = max(80, settings.max_tool_calls * 5 + 20)
        if process_mode:
            recursion_limit = max(recursion_limit, settings.max_tool_calls * 6 + 30)
        final_state = graph.invoke(
            initial,
            config={"recursion_limit": recursion_limit},
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
