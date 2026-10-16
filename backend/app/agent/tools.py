"""Deterministic claim investigation tools."""

from __future__ import annotations

import inspect
import json
import re
from collections import Counter
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Dict, List, Optional

from app.data.loader import (
    get_claim,
    get_claim_documents,
    get_line_items,
    get_policy,
    load_claims,
    load_policies,
    load_required_docs,
)
from app.data.models import coerce_citation_dict, normalize_retrieved_evidence
from app.events.bus import event_bus
from app.rag.hybrid import hybrid_search

TOOL_NODE_MAP = {
    "get_claim_details": "claim_lookup",
    "search_policy_documents": "hybrid_retrieval",
    "validate_policy_dates": "coverage_check",  # date validation shares coverage branch visuals
    "check_coverage_facts": "coverage_check",
    "analyze_repair_estimate": "estimate_analysis",
    "check_missing_documents": "missing_documents",
    "find_similar_claims": "similar_claims",
    "query_portfolio_data": "portfolio_lookup",
    "generate_investigation_report": "report_generator",
}


def _money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def get_claim_details(claim_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    claim = get_claim(claim_id)
    policy = get_policy(claim.policy_id)
    result = {
        "claim_id": claim.claim_id,
        "policy_id": claim.policy_id,
        "vehicle": claim.vehicle.model_dump(),
        "accident_date": claim.accident_date,
        "accident_description": claim.accident_description,
        "claim_status": claim.claim_status,
        "submitted_documents": claim.submitted_documents,
        "location": claim.location,
        "estimate_total": claim.estimate_total,
        "insured_name": policy.insured_name,
        "jurisdiction": policy.jurisdiction,
    }
    return result


def search_policy_documents(
    policy_id: str, question: str, run_id: Optional[str] = None
) -> Dict[str, Any]:
    return hybrid_search(question=question, policy_id=policy_id, run_id=run_id)


def validate_policy_dates(
    policy_id: str, loss_date: str, run_id: Optional[str] = None
) -> Dict[str, Any]:
    policy = get_policy(policy_id)
    effective = _parse_date(policy.effective_date)
    expiration = _parse_date(policy.expiration_date)
    loss = _parse_date(loss_date)
    within = effective <= loss <= expiration
    unresolved = []
    if policy.status != "active":
        unresolved.append(
            f"Policy status is '{policy.status}'. Confirm cancellation/renewal history with underwriting."
        )
    if not within:
        unresolved.append(
            "Loss date falls outside the Declarations period. Confirm late-reported continuity or renewal gaps."
        )
    unresolved.append(
        "Date-range membership alone does not establish legal coverage, causation, or entitlement."
    )
    return {
        "policy_id": policy_id,
        "effective_date": policy.effective_date,
        "expiration_date": policy.expiration_date,
        "loss_date": loss_date,
        "loss_date_within_period": within,
        "policy_status": policy.status,
        "unresolved_policy_status_questions": unresolved,
    }


def check_coverage_facts(claim_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    claim = get_claim(claim_id)
    policy = get_policy(claim.policy_id)
    listed = list(policy.coverages)
    collision_listed = "Collision" in listed
    comprehensive_listed = "Comprehensive" in listed
    questions = [
        "Confirm whether the loss cause maps to Collision, Comprehensive, or Liability under the policy definitions.",
        "Confirm whether any exclusion or endorsement modifies the listed coverages for this loss.",
        "A coverage type being listed does not by itself establish legal coverage for this claim.",
    ]
    if collision_listed:
        collision_status = "Collision coverage is listed on the policy."
    else:
        collision_status = "Collision coverage is not listed on the policy."
    if comprehensive_listed:
        comprehensive_status = "Comprehensive coverage is listed on the policy."
    else:
        comprehensive_status = "Comprehensive coverage is not listed on the policy."
    return {
        "claim_id": claim_id,
        "policy_id": policy.policy_id,
        "listed_coverage_types": listed,
        "collision_listed": collision_listed,
        "comprehensive_listed": comprehensive_listed,
        "collision_status": collision_status,
        "comprehensive_status": comprehensive_status,
        "summary": (
            f"Listed coverages: {', '.join(listed)}. {collision_status} "
            f"Collision deductible: ${policy.collision_deductible:.2f}."
        ),
        "collision_deductible": policy.collision_deductible,
        "comprehensive_deductible": policy.comprehensive_deductible,
        "endorsements": policy.endorsements,
        "policy_form_version": policy.policy_form_version,
        "relevant_policy_references": [
            f"{policy.policy_id} Declarations",
            "Section 3 — Collision Coverage",
            "Section 4 — Comprehensive Coverage",
            "Section 6 — Exclusions",
        ],
        "coverage_questions_requiring_review": questions,
    }


def analyze_repair_estimate(claim_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    claim = get_claim(claim_id)
    policy = get_policy(claim.policy_id)
    items = get_line_items(claim_id)

    line_rows = []
    computed_total = Decimal("0.00")
    arithmetic_issues: List[str] = []
    for item in items:
        expected = _money(
            Decimal(str(item.labor_hours)) * Decimal(str(item.labor_rate))
            + Decimal(str(item.parts_cost))
        )
        reported = _money(item.total)
        if expected != reported:
            arithmetic_issues.append(
                f"{item.line_id} '{item.description}': expected {expected}, reported {reported}"
            )
        computed_total += reported
        line_rows.append(item.model_dump())

    # Potential duplicates by description + part_number
    keys = [(i.description.lower().strip(), (i.part_number or "").lower()) for i in items]
    counts = Counter(keys)
    potential_duplicates = []
    for (desc, part), count in counts.items():
        if count > 1:
            potential_duplicates.append(
                {
                    "description": desc,
                    "part_number": part,
                    "occurrences": count,
                    "note": "Potential duplicate charge — do not auto-remove; flag for human review.",
                }
            )

    submitted_total = _money(claim.estimate_total)
    deductible = _money(policy.collision_deductible)
    illustrative_net = submitted_total - deductible
    if illustrative_net < Decimal("0.00"):
        illustrative_net = Decimal("0.00")

    return {
        "claim_id": claim_id,
        "repair_line_items": line_rows,
        "submitted_total": float(submitted_total),
        "sum_of_line_items": float(computed_total),
        "potential_duplicate_charges": potential_duplicates,
        "arithmetic_inconsistencies": arithmetic_issues,
        "illustrative_net_amount": float(illustrative_net),
        "illustrative_deductible_applied": float(deductible),
        "notes": [
            "Arithmetic is computed with Decimal precision in code, not by an LLM.",
            "Potential duplicates are flagged only; charges are not removed automatically.",
            "Illustrative net amount is not a settlement offer.",
        ],
    }


def check_missing_documents(claim_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    claim = get_claim(claim_id)
    checklist = load_required_docs()
    tag = (claim.scenario_tag or "").lower()
    if "comprehensive" in tag or "hail" in tag or "theft" in tag or "flood" in tag or "vandal" in tag or "glass" in tag:
        required = checklist.get("comprehensive", checklist["default"])
    else:
        required = checklist.get("collision", checklist["default"])

    submitted = list(claim.submitted_documents)
    missing = [d for d in required if d not in submitted]
    recommendations = [f"Request {d} from claimant or repair facility." for d in missing]
    if not missing:
        recommendations.append("Core checklist appears complete; verify document authenticity.")
    return {
        "claim_id": claim_id,
        "submitted_documents": submitted,
        "required_documents": required,
        "missing_documents": missing,
        "recommended_evidence_requests": recommendations,
        "document_records": [d.model_dump() for d in get_claim_documents(claim_id)],
    }


def query_portfolio_data(
    query_type: str = "summary",
    status: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Answer portfolio-level questions from local JSON (no claim_id required)."""
    policies = list(load_policies().values())
    claims = list(load_claims().values())
    status_filter = (status or "").strip().lower() or None
    q = (query_type or "summary").strip().lower()

    def _policy_row(p: Any) -> Dict[str, Any]:
        return {
            "policy_id": p.policy_id,
            "insured_name": p.insured_name,
            "status": p.status,
            "effective_date": p.effective_date,
            "expiration_date": p.expiration_date,
            "jurisdiction": p.jurisdiction,
            "coverages": list(p.coverages),
        }

    def _claim_row(c: Any) -> Dict[str, Any]:
        return {
            "claim_id": c.claim_id,
            "policy_id": c.policy_id,
            "claim_status": c.claim_status,
            "accident_date": c.accident_date,
            "scenario_tag": c.scenario_tag,
        }

    by_policy_status: Dict[str, int] = {}
    for p in policies:
        key = str(p.status).lower()
        by_policy_status[key] = by_policy_status.get(key, 0) + 1

    by_claim_status: Dict[str, int] = {}
    for c in claims:
        key = str(c.claim_status).lower()
        by_claim_status[key] = by_claim_status.get(key, 0) + 1

    filtered_policies = [
        _policy_row(p)
        for p in policies
        if not status_filter or str(p.status).lower() == status_filter
    ]
    filtered_claims = [
        _claim_row(c)
        for c in claims
        if not status_filter or str(c.claim_status).lower() == status_filter
    ]
    active_ids = [p.policy_id for p in policies if str(p.status).lower() == "active"]

    result: Dict[str, Any] = {
        "query_type": q,
        "status_filter": status_filter,
        "source": "local policies.json / claims.json",
        "policy_count_total": len(policies),
        "claim_count_total": len(claims),
        "policies_by_status": by_policy_status,
        "claims_by_status": by_claim_status,
        "active_policy_count": len(active_ids),
        "active_policy_ids": active_ids,
        "note": (
            f"{len(active_ids)} active policies out of {len(policies)} total; "
            f"{len(claims)} claims in the synthetic dataset."
        ),
    }

    if q in {"list_policies", "policies", "active_policies", "count_policies"}:
        rows = filtered_policies
        if q == "active_policies" and not status_filter:
            rows = [r for r in (_policy_row(p) for p in policies) if str(r["status"]).lower() == "active"]
        result["policies"] = rows
        result["matched_policy_count"] = len(rows)
    elif q in {"list_claims", "claims", "count_claims"}:
        result["claims"] = filtered_claims
        result["matched_claim_count"] = len(filtered_claims)
    else:
        result["policies"] = filtered_policies if status_filter else [
            _policy_row(p) for p in policies
        ]

    return result


def find_similar_claims(claim_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    source = get_claim(claim_id)
    others = [c for c in load_claims().values() if c.claim_id != claim_id]
    src_tokens = set(re.findall(r"[a-z0-9]+", source.accident_description.lower()))
    src_tokens |= {source.vehicle.make.lower(), source.vehicle.model.lower()}
    ranked = []
    for other in others:
        tokens = set(re.findall(r"[a-z0-9]+", other.accident_description.lower()))
        tokens |= {other.vehicle.make.lower(), other.vehicle.model.lower()}
        overlap = src_tokens & tokens
        score = len(overlap) / max(1, len(src_tokens | tokens))
        if source.scenario_tag and source.scenario_tag == other.scenario_tag:
            score += 0.15
        if source.vehicle.make == other.vehicle.make:
            score += 0.05
        ranked.append((score, other, sorted(overlap)[:12]))
    ranked.sort(key=lambda x: x[0], reverse=True)
    similar = []
    for score, other, overlap in ranked[:5]:
        similar.append(
            {
                "claim_id": other.claim_id,
                "similarity_score": round(float(score), 4),
                "accident_description": other.accident_description,
                "scenario_tag": other.scenario_tag,
                "shared_terms": overlap,
                "investigation_pattern": (
                    "Review policy dates, listed coverages, estimate integrity, and missing docs."
                ),
                "caveat": "Historical claims are reference information, not binding coverage precedents.",
            }
        )
    return {
        "claim_id": claim_id,
        "similar_claims": similar,
        "disclaimer": "Similarity is illustrative for investigation patterns only.",
    }


def _force_citation_dict(item: Any) -> Dict[str, Any]:
    """Convert any LLM evidence item into a plain citation dict (no nested Pydantic fail)."""
    return coerce_citation_dict(item)


def _as_plain_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: List[str] = []
        for v in value:
            if isinstance(v, str):
                out.append(v)
            else:
                out.append(json.dumps(v, default=str)[:300])
        return out
    return [str(value)]


def generate_investigation_report(
    claim_id: str,
    claim_summary: str = "",
    policy_facts: Optional[Dict[str, Any]] = None,
    retrieved_evidence: Optional[Any] = None,
    coverage_considerations: Optional[Any] = None,
    estimate_analysis: Optional[Any] = None,
    potential_discrepancies: Optional[Any] = None,
    missing_documents: Optional[Any] = None,
    illustrative_financials: Optional[Any] = None,
    recommended_next_steps: Optional[Any] = None,
    unresolved_questions: Optional[Any] = None,
    investigation_status: str = "pending_human_review",
    human_review_required: bool = True,
    run_id: Optional[str] = None,
    **_extra: Any,
) -> Dict[str, Any]:
    """Build report as a plain dict — never raises on LLM shape errors."""
    try:
        evidence = [
            _force_citation_dict(x) for x in normalize_retrieved_evidence(retrieved_evidence)
        ]
    except Exception:  # noqa: BLE001
        evidence = [
            {
                "document_name": "Investigation note",
                "excerpt": str(retrieved_evidence)[:500],
            }
        ]
    needs_human = True if human_review_required is None else bool(human_review_required)
    return {
        "claim_id": str(claim_id or "unknown"),
        "investigation_status": investigation_status or "pending_human_review",
        "claim_summary": claim_summary or f"Investigation summary for {claim_id}",
        "policy_facts": policy_facts if isinstance(policy_facts, dict) else {},
        "retrieved_evidence": evidence,
        "coverage_considerations": _as_plain_str_list(coverage_considerations),
        "estimate_analysis": estimate_analysis if isinstance(estimate_analysis, dict) else {},
        "potential_discrepancies": _as_plain_str_list(potential_discrepancies),
        "missing_documents": _as_plain_str_list(missing_documents),
        "illustrative_financials": (
            illustrative_financials if isinstance(illustrative_financials, dict) else {}
        ),
        "recommended_next_steps": _as_plain_str_list(recommended_next_steps)
        or [
            "Have a licensed adjuster review all evidence and tool outputs.",
            "Do not approve, deny, settle, or pay based on this report alone.",
        ],
        "unresolved_questions": _as_plain_str_list(unresolved_questions),
        "human_review_required": needs_human or True,
        "disclaimer": (
            "This report is an investigative aid only. It does not approve, deny, "
            "settle, or pay any claim. Final decisions require licensed human review. "
            "Policy-date checks and coverage flags alone do not establish legal coverage."
        ),
        "report_builder": "v5_plain_dict",
    }


TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_claim_details",
            "description": "Look up structured claim intake details by claim_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                },
                "required": ["claim_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy_documents",
            "description": "Hybrid BM25 + Pinecone + RRF search over policy documents for a policy_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_id": {"type": "string"},
                    "question": {"type": "string"},
                },
                "required": ["policy_id", "question"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_policy_dates",
            "description": "Check whether loss_date falls within policy effective/expiration dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_id": {"type": "string"},
                    "loss_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                },
                "required": ["policy_id", "loss_date"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_coverage_facts",
            "description": "Return listed coverages, deductibles, and open coverage questions. Does not decide coverage.",
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
            "name": "analyze_repair_estimate",
            "description": "Analyze repair line items with precise arithmetic; flag duplicates without removing them.",
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
            "name": "check_missing_documents",
            "description": "Compare submitted documents against the synthetic required checklist.",
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
            "name": "find_similar_claims",
            "description": "Retrieve similar synthetic historical claims for investigation patterns only.",
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
            "name": "query_portfolio_data",
            "description": (
                "Answer portfolio / dataset questions that are NOT tied to one claim "
                "(e.g. how many policies are active, list policies, count claims). "
                "Reads local policies.json and claims.json. Use when no claim_id is selected "
                "or the question is about the whole book of business."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "description": (
                            "summary | list_policies | active_policies | count_policies | "
                            "list_claims | count_claims"
                        ),
                    },
                    "status": {
                        "type": "string",
                        "description": "Optional filter, e.g. active or expired for policies.",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_investigation_report",
            "description": (
                "Produce the final structured investigation report JSON for human review. "
                "claim_summary must directly answer the user's Question (1–3 sentences), "
                "not a generic full claim narrative."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                    "claim_summary": {
                        "type": "string",
                        "description": (
                            "Direct answer to the user's Question in 1–3 sentences, including "
                            "key dates/facts (e.g. loss date within effective–expiration). "
                            "Do not paste the full FNOL accident story unless asked."
                        ),
                    },
                    "policy_facts": {"type": "object"},
                    "retrieved_evidence": {
                        "type": "array",
                        "description": (
                            "Policy citations only. Each item must include document_name and excerpt "
                            "(from search_policy_documents citations). Put tool facts in policy_facts."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "document_name": {"type": "string"},
                                "section": {"type": "string"},
                                "page_number": {"type": ["integer", "null"]},
                                "excerpt": {"type": "string"},
                                "chunk_id": {"type": "string"},
                                "score": {"type": "number"},
                            },
                        },
                    },
                    "coverage_considerations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "estimate_analysis": {"type": "object"},
                    "potential_discrepancies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "missing_documents": {"type": "array", "items": {"type": "string"}},
                    "illustrative_financials": {"type": "object"},
                    "recommended_next_steps": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "unresolved_questions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "investigation_status": {"type": "string"},
                    "human_review_required": {
                        "type": "boolean",
                        "description": "Must be true. Final claim decisions require a human adjuster.",
                    },
                },
                "required": ["claim_id", "claim_summary"],
                "additionalProperties": True,
            },
        },
    },
]


IMPLEMENTATIONS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "get_claim_details": get_claim_details,
    "search_policy_documents": search_policy_documents,
    "validate_policy_dates": validate_policy_dates,
    "check_coverage_facts": check_coverage_facts,
    "analyze_repair_estimate": analyze_repair_estimate,
    "check_missing_documents": check_missing_documents,
    "find_similar_claims": find_similar_claims,
    "query_portfolio_data": query_portfolio_data,
    "generate_investigation_report": generate_investigation_report,
}


def execute_tool(
    name: str, arguments: Dict[str, Any], run_id: Optional[str] = None
) -> Dict[str, Any]:
    if name not in IMPLEMENTATIONS:
        raise ValueError(f"Unknown tool: {name}")
    fn = IMPLEMENTATIONS[name]
    kwargs = dict(arguments or {})
    if "run_id" in inspect.signature(fn).parameters:
        kwargs["run_id"] = run_id

    # Drop unexpected LLM keys unless the function accepts **kwargs
    sig = inspect.signature(fn)
    accepts_var_kw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    if not accepts_var_kw:
        kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}

    try:
        return fn(**kwargs)
    except TypeError as exc:
        # Last resort for report tool: strip unknowns and retry / fallback
        if name == "generate_investigation_report":
            allowed = {
                k: v
                for k, v in dict(arguments or {}).items()
                if k
                in {
                    "claim_id",
                    "claim_summary",
                    "policy_facts",
                    "retrieved_evidence",
                    "coverage_considerations",
                    "estimate_analysis",
                    "potential_discrepancies",
                    "missing_documents",
                    "illustrative_financials",
                    "recommended_next_steps",
                    "unresolved_questions",
                    "investigation_status",
                    "human_review_required",
                }
            }
            allowed["claim_id"] = str(allowed.get("claim_id") or "unknown")
            try:
                return generate_investigation_report(**allowed)
            except Exception as inner:  # noqa: BLE001
                return generate_investigation_report(
                    claim_id=str(allowed.get("claim_id") or "unknown"),
                    claim_summary=str(allowed.get("claim_summary") or ""),
                    retrieved_evidence=allowed.get("retrieved_evidence"),
                    unresolved_questions=[f"Recovered from tool error: {inner}"],
                )
        raise exc
    except Exception as exc:  # noqa: BLE001
        if name == "generate_investigation_report":
            return generate_investigation_report(
                claim_id=str((arguments or {}).get("claim_id") or "unknown"),
                claim_summary=str((arguments or {}).get("claim_summary") or ""),
                retrieved_evidence=(arguments or {}).get("retrieved_evidence"),
                unresolved_questions=[f"Recovered from tool error: {exc}"],
            )
        raise


def tool_result_json(result: Any) -> str:
    return json.dumps(result, default=str)
