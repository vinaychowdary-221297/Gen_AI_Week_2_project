"""Week 3 tools: classify, docs/estimates, Keenable search, human handoff."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.agent.estimate_docs import (
    build_preliminary_from_claim,
    compare_estimates,
    list_claim_files,
    load_estimate_document,
)
from app.clients.keenable import KeenableError, get_keenable
from app.config import get_settings
from app.data.loader import get_claim, get_policy, load_required_docs


def classify_claim(claim_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    claim = get_claim(claim_id)
    tag = (claim.scenario_tag or "").lower()
    desc = (claim.accident_description or "").lower()

    if "hail" in tag or "theft" in tag or "flood" in tag or "vandal" in tag or "glass" in tag:
        loss_type = "comprehensive"
    elif "collision" in tag or "rear" in desc or "side-swipe" in desc or "t-bone" in desc:
        loss_type = "collision"
    elif "expir" in tag:
        loss_type = "collision"
    else:
        loss_type = "collision"

    if "expir" in tag:
        track = "expired_policy"
        severity = "high"
        flags = ["policy_period_risk"]
    elif "duplicate" in tag:
        track = "duplicate_review"
        severity = "medium"
        flags = ["estimate_integrity"]
    elif "no_collision" in tag:
        track = "coverage_gap_review"
        severity = "medium"
        flags = ["collision_not_listed"]
    elif "comprehensive" in tag or loss_type == "comprehensive":
        track = "comprehensive"
        severity = "medium" if claim.estimate_total < 6000 else "high"
        flags = []
    else:
        track = "standard"
        severity = "low" if claim.estimate_total < 3000 else ("high" if claim.estimate_total > 7000 else "medium")
        flags = []

    auto_escalate = severity == "high" or "policy_period_risk" in flags
    return {
        "claim_id": claim_id,
        "loss_type": loss_type,
        "severity": severity,
        "recommended_track": track,
        "flags": flags,
        "scenario_tag": claim.scenario_tag,
        "vehicle_at_facility": bool(getattr(claim, "vehicle_at_facility", False)),
        "auto_escalate_to_human": auto_escalate,
        "rationale": (
            f"Classified as {loss_type}/{severity} on track '{track}' from scenario "
            f"'{claim.scenario_tag}' and estimate_total={claim.estimate_total}."
        ),
        "disclaimer": "Classification routes investigation only; it is not a coverage or payment decision.",
    }


def list_claim_documents(claim_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    claim = get_claim(claim_id)
    files = list_claim_files(claim_id)
    checklist = load_required_docs()
    tag = (claim.scenario_tag or "").lower()
    if any(k in tag for k in ("comprehensive", "hail", "theft", "flood", "vandal", "glass")):
        required = checklist.get("comprehensive", checklist["default"])
    else:
        required = checklist.get("collision", checklist["default"])
    filenames = {f["filename"].lower() for f in files}
    present_types = []
    for req in required:
        key = req.lower().replace(" ", "_")
        found = any(key in fn or req.lower() in fn for fn in filenames)
        if found or req in claim.submitted_documents:
            present_types.append(req)
    missing = [d for d in required if d not in present_types and d not in claim.submitted_documents]
    return {
        "claim_id": claim_id,
        "files_on_disk": files,
        "submitted_documents": claim.submitted_documents,
        "required_checklist": required,
        "missing_documents": missing,
        "vehicle_at_facility": bool(getattr(claim, "vehicle_at_facility", False)),
        "note": "File presence under data/claims/{id}/ plus FNOL submitted list.",
    }


def parse_repair_estimate_document(
    claim_id: str,
    estimate_type: str = "facility",
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    return load_estimate_document(claim_id, estimate_type=estimate_type)


def build_preliminary_estimate(
    claim_id: str,
    use_web_research: bool = True,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    doc = load_estimate_document(claim_id, estimate_type="preliminary")
    if doc.get("line_items"):
        base = doc
    else:
        base = build_preliminary_from_claim(claim_id)

    market: Dict[str, Any] = {"skipped": True}
    if use_web_research:
        try:
            market = research_market_repair_costs(claim_id, run_id=run_id)
        except Exception as exc:  # noqa: BLE001
            market = {"error": str(exc), "retry_suggested": True}

    return {
        **base,
        "market_research": market,
        "disclaimer": (
            "Preliminary estimate based on information on file; may change after the vehicle "
            "is at a repair facility. Illustrative only — not a settlement offer."
        ),
    }


def compare_estimate_versions(claim_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    preliminary = load_estimate_document(claim_id, "preliminary")
    if not preliminary.get("line_items"):
        preliminary = build_preliminary_from_claim(claim_id)
    facility = load_estimate_document(claim_id, "facility")
    comparison = compare_estimates(preliminary, facility)
    return {
        "claim_id": claim_id,
        "preliminary": {
            "grand_total": preliminary.get("grand_total"),
            "source": preliminary.get("source"),
            "line_count": len(preliminary.get("line_items") or []),
        },
        "facility": {
            "grand_total": facility.get("grand_total"),
            "source": facility.get("source"),
            "line_count": len(facility.get("line_items") or []),
        },
        "comparison": comparison,
    }


def search_web(query: str, claim_id: Optional[str] = None, run_id: Optional[str] = None) -> Dict[str, Any]:
    client = get_keenable()
    result = client.search(query)
    result["claim_id"] = claim_id
    result["tool"] = "search_web"
    return result


def research_market_repair_costs(
    claim_id: str, run_id: Optional[str] = None
) -> Dict[str, Any]:
    settings = get_settings()
    claim = get_claim(claim_id)
    v = claim.vehicle
    facility = load_estimate_document(claim_id, "facility")
    items = facility.get("line_items") or build_preliminary_from_claim(claim_id).get("line_items") or []
    limit = settings.keenable_market_line_limit
    client = get_keenable()
    researched: List[Dict[str, Any]] = []
    errors: List[str] = []

    queries: List[Tuple[str, str]] = []
    for item in items[:limit]:
        desc = str(item.get("description") or "")
        q = f"{v.year} {v.make} {v.model} {desc} replacement cost USD"
        queries.append((desc, q))
    # Labor rate context
    loc = (claim.location or "").split(",")[-1].strip() or "US"
    queries.append(("body_labor_rate", f"auto body shop labor rate {loc} USD per hour"))

    for label, query in queries:
        try:
            hit = client.search(query, max_results=3)
            researched.append(
                {
                    "line": label,
                    "query": query,
                    "answer": hit.get("answer"),
                    "results": hit.get("results", [])[:3],
                }
            )
        except KeenableError as exc:
            errors.append(f"{label}: {exc}")

    return {
        "claim_id": claim_id,
        "researched": researched,
        "errors": errors,
        "disclaimer": (
            "Market figures from public web search are illustrative ranges only. "
            "Do not treat as OEM invoice or settlement authority. Human review required."
        ),
    }


def build_illustrative_market_estimate(
    claim_id: str, run_id: Optional[str] = None
) -> Dict[str, Any]:
    facility = load_estimate_document(claim_id, "facility")
    market = research_market_repair_costs(claim_id, run_id=run_id)
    return {
        "claim_id": claim_id,
        "shop_estimate_total": facility.get("grand_total"),
        "shop_source": facility.get("source"),
        "market_research": market,
        "note": (
            "Side-by-side market research attached. Extracted dollar amounts from web snippets "
            "are unreliable; use URLs for adjuster follow-up. Not a payment recommendation."
        ),
    }


def request_human_handoff(
    reason: str,
    blocking_questions: Optional[Any] = None,
    claim_id: Optional[str] = None,
    from_stage: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    questions: List[str] = []
    if isinstance(blocking_questions, list):
        questions = [str(q) for q in blocking_questions]
    elif isinstance(blocking_questions, str) and blocking_questions.strip():
        questions = [blocking_questions]
    return {
        "handoff_requested": True,
        "claim_id": claim_id,
        "from_stage": from_stage or "investigation",
        "reason": reason or "Agent requested human adjuster review.",
        "blocking_questions": questions,
        "status": "awaiting_human",
        "human_review_required": True,
        "disclaimer": (
            "Autonomous processing stopped. A licensed human adjuster must continue. "
            "No approval, denial, settlement, or payment has been made."
        ),
    }


WEEK3_TOOL_NODE_MAP = {
    "classify_claim": "classification",
    "list_claim_documents": "claim_documents",
    "parse_repair_estimate_document": "estimate_parse",
    "build_preliminary_estimate": "preliminary_estimate",
    "compare_estimate_versions": "estimate_compare",
    "search_web": "web_search",
    "research_market_repair_costs": "market_research",
    "build_illustrative_market_estimate": "market_estimate",
    "request_human_handoff": "human_handoff",
}

WEEK3_IMPLEMENTATIONS = {
    "classify_claim": classify_claim,
    "list_claim_documents": list_claim_documents,
    "parse_repair_estimate_document": parse_repair_estimate_document,
    "build_preliminary_estimate": build_preliminary_estimate,
    "compare_estimate_versions": compare_estimate_versions,
    "search_web": search_web,
    "research_market_repair_costs": research_market_repair_costs,
    "build_illustrative_market_estimate": build_illustrative_market_estimate,
    "request_human_handoff": request_human_handoff,
}

WEEK3_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "classify_claim",
            "description": "Classify loss type, severity, and investigation track for a claim (routing only).",
            "parameters": {
                "type": "object",
                "properties": {"claim_id": {"type": "string"}},
                "required": ["claim_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_claim_documents",
            "description": "List claim folder files and missing checklist documents.",
            "parameters": {
                "type": "object",
                "properties": {"claim_id": {"type": "string"}},
                "required": ["claim_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "parse_repair_estimate_document",
            "description": "Parse preliminary or facility repair estimate Markdown for a claim.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                    "estimate_type": {
                        "type": "string",
                        "description": "preliminary or facility",
                    },
                },
                "required": ["claim_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_preliminary_estimate",
            "description": (
                "Build/load a preliminary desk estimate from info on file; optionally enrich with Keenable web search. "
                "Subject to change at repair facility. Not a settlement."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                    "use_web_research": {"type": "boolean"},
                },
                "required": ["claim_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_estimate_versions",
            "description": "Compare preliminary vs facility estimates and flag changes after shop intake.",
            "parameters": {
                "type": "object",
                "properties": {"claim_id": {"type": "string"}},
                "required": ["claim_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Keenable web search for public facts (weather, recalls, market context). Cite URLs; do not invent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "claim_id": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "research_market_repair_costs",
            "description": "Keenable research for parts/labor market context on top estimate lines. Illustrative only.",
            "parameters": {
                "type": "object",
                "properties": {"claim_id": {"type": "string"}},
                "required": ["claim_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_illustrative_market_estimate",
            "description": "Combine shop estimate with Keenable market research for adjuster comparison. Not payment authority.",
            "parameters": {
                "type": "object",
                "properties": {"claim_id": {"type": "string"}},
                "required": ["claim_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_human_handoff",
            "description": (
                "Stop autonomous work and hand off to a human adjuster when blocked, "
                "evidence is insufficient, or tools keep failing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "blocking_questions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "claim_id": {"type": "string"},
                    "from_stage": {"type": "string"},
                },
                "required": ["reason"],
                "additionalProperties": False,
            },
        },
    },
]
