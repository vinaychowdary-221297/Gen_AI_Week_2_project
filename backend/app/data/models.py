"""Pydantic models for claims data and investigation reports."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Vehicle(BaseModel):
    year: int
    make: str
    model: str
    trim: Optional[str] = None
    vin: Optional[str] = None
    color: Optional[str] = None


class PolicyRecord(BaseModel):
    policy_id: str
    insured_name: str
    jurisdiction: str
    effective_date: str
    expiration_date: str
    policy_form_version: str
    coverages: List[str]
    collision_deductible: float
    comprehensive_deductible: float
    liability_limit_bodily: int
    liability_limit_property: int
    vehicle: Vehicle
    endorsements: List[str] = Field(default_factory=list)
    status: str = "active"


class ClaimDocument(BaseModel):
    document_id: str
    claim_id: str
    document_type: str
    filename: str
    submitted: bool = True
    notes: Optional[str] = None


class RepairLineItem(BaseModel):
    line_id: str
    claim_id: str
    description: str
    part_number: Optional[str] = None
    labor_hours: float = 0.0
    labor_rate: float = 0.0
    parts_cost: float = 0.0
    total: float = 0.0


class ClaimRecord(BaseModel):
    claim_id: str
    policy_id: str
    accident_date: str
    accident_description: str
    claim_status: str
    vehicle: Vehicle
    reported_date: str
    location: str
    police_report_number: Optional[str] = None
    submitted_documents: List[str] = Field(default_factory=list)
    estimate_total: float = 0.0
    scenario_tag: Optional[str] = None
    notes: Optional[str] = None


class Citation(BaseModel):
    document_name: str = Field(default="Supporting evidence")
    section: Optional[str] = None
    page_number: Optional[int] = None
    excerpt: str = Field(default="")
    chunk_id: Optional[str] = None
    score: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_loose_shapes(cls, data: Any) -> Any:
        """Accept LLM citation variants before field validation."""
        if data is None:
            return {"document_name": "Supporting evidence", "excerpt": ""}
        if isinstance(data, str):
            return {"document_name": "Investigation note", "excerpt": data[:500]}
        if not isinstance(data, dict):
            return {"document_name": "Investigation note", "excerpt": str(data)[:500]}

        # Already fine
        if data.get("document_name") and (data.get("excerpt") or data.get("chunk_text")):
            return {
                **data,
                "excerpt": data.get("excerpt") or data.get("chunk_text"),
            }

        # {type: policy, citation: "..."} or citations as a string
        citation_str = data.get("citation")
        if citation_str is None and isinstance(data.get("citations"), str):
            citation_str = data.get("citations")

        label = str(data.get("type") or data.get("tool") or "evidence")
        doc = (
            data.get("document_name")
            or data.get("source")
            or data.get("source_filename")
            or data.get("document_id")
            or data.get("title")
            or data.get("name")
            or data.get("file")
            or data.get("filename")
            or data.get("policy_id")
        )
        excerpt = (
            data.get("excerpt")
            or data.get("chunk_text")
            or data.get("text")
            or data.get("content")
            or data.get("clause")
            or data.get("body")
            or data.get("quote")
            or data.get("passage")
            or citation_str
            or data.get("summary")
            or data.get("collision_status")
            or data.get("accident_description")
            or data.get("section")  # LLM sometimes only sends source+section
        )

        if not excerpt:
            if "loss_date_within_period" in data:
                within = data.get("loss_date_within_period")
                excerpt = (
                    f"Loss date {data.get('loss_date')} "
                    f"{'is within' if within else 'is outside'} policy period "
                    f"{data.get('effective_date')} to {data.get('expiration_date')}."
                )
            elif (
                data.get("illustrative_net_amount") is not None
                or data.get("submitted_total") is not None
                or data.get("after_deductible") is not None
                or data.get("amount_after_deductible") is not None
                or data.get("net_after_deductible") is not None
            ):
                excerpt = (
                    f"Estimate submitted={data.get('submitted_total')} "
                    f"net={data.get('illustrative_net_amount') or data.get('net_after_deductible') or data.get('after_deductible') or data.get('amount_after_deductible')} "
                    f"deductible={data.get('illustrative_deductible_applied') or data.get('deductible')}"
                )
            elif data.get("missing_documents") is not None or data.get("missing") is not None:
                excerpt = f"Missing documents: {data.get('missing_documents') or data.get('missing')}"
            elif label in ("repair_estimate", "estimate_analysis", "missing_documents", "missing_document"):
                excerpt = json.dumps(data, default=str)[:500]
            elif isinstance(data.get("citations"), list):
                # flatten later at list level; keep a placeholder here
                excerpt = json.dumps(data.get("citations"), default=str)[:500]
            else:
                excerpt = json.dumps(data, default=str)[:500]

        if not doc:
            doc = (
                f"Policy evidence ({label})"
                if "policy" in label.lower()
                else f"Tool evidence ({label})"
            )

        return {
            "document_name": str(doc),
            "section": data.get("section") or ("Policy" if label == "policy" else "Structured tool output"),
            "page_number": data.get("page_number"),
            "excerpt": str(excerpt)[:500],
            "chunk_id": data.get("chunk_id"),
            "score": data.get("score") or data.get("rrf_score"),
        }

    @field_validator("page_number", mode="before")
    @classmethod
    def _coerce_page(cls, v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None


def normalize_retrieved_evidence(raw: Any) -> List[Any]:
    """Flatten and prepare evidence items for Citation coercion."""
    if raw is None:
        return []
    if isinstance(raw, dict):
        # Sometimes the whole hybrid payload is one object
        if isinstance(raw.get("citations"), list):
            return normalize_retrieved_evidence(raw["citations"])
        return [raw]
    if not isinstance(raw, list):
        return [raw]

    out: List[Any] = []
    for item in raw:
        if item is None:
            continue
        if isinstance(item, dict):
            nested = item.get("citations")
            if isinstance(nested, list) and nested and not item.get("excerpt"):
                # Expand nested citation lists; keep parent hint as type=policy
                for n in nested:
                    if isinstance(n, dict):
                        out.append({**n, "type": n.get("type") or item.get("type") or "policy"})
                    else:
                        out.append(
                            {
                                "type": item.get("type") or "policy",
                                "citation": str(n),
                                "document_name": item.get("document_name") or "Policy document",
                            }
                        )
                continue
        out.append(item)
    return out


def coerce_citation_dict(item: Any) -> Dict[str, Any]:
    """Always return a plain citation dict — never raises (no nested Pydantic)."""
    if isinstance(item, str):
        return {
            "document_name": "Investigation note",
            "section": None,
            "page_number": None,
            "excerpt": item[:500],
            "chunk_id": None,
            "score": None,
        }
    if not isinstance(item, dict):
        return {
            "document_name": "Investigation note",
            "section": None,
            "page_number": None,
            "excerpt": str(item)[:500],
            "chunk_id": None,
            "score": None,
        }

    label = str(item.get("type") or item.get("tool") or "evidence")
    doc = (
        item.get("document_name")
        or item.get("source")
        or item.get("source_filename")
        or item.get("document_id")
        or item.get("title")
        or item.get("name")
        or item.get("file")
        or item.get("filename")
        or item.get("policy_id")
        or (f"Policy evidence ({label})" if "policy" in label.lower() else f"Tool evidence ({label})")
    )
    excerpt = (
        item.get("excerpt")
        or item.get("chunk_text")
        or item.get("text")
        or item.get("content")
        or item.get("clause")
        or item.get("body")
        or item.get("quote")
        or item.get("passage")
        or item.get("citation")
        or (item.get("citations") if isinstance(item.get("citations"), str) else None)
        or item.get("summary")
        or item.get("collision_status")
        or item.get("accident_description")
        or item.get("section")
        or json.dumps(item, default=str)
    )
    page = item.get("page_number")
    try:
        page_number = int(page) if page is not None and page != "" else None
    except (TypeError, ValueError):
        page_number = None
    return {
        "document_name": str(doc),
        "section": item.get("section"),
        "page_number": page_number,
        "excerpt": str(excerpt)[:500],
        "chunk_id": item.get("chunk_id"),
        "score": item.get("score") or item.get("rrf_score"),
    }


class InvestigationReport(BaseModel):
    claim_id: str
    investigation_status: str = "pending_human_review"
    claim_summary: str = ""
    policy_facts: Dict[str, Any] = Field(default_factory=dict)
    # Plain dicts — never nest Citation validation (LLM shapes vary widely)
    retrieved_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    coverage_considerations: List[str] = Field(default_factory=list)
    estimate_analysis: Dict[str, Any] = Field(default_factory=dict)
    potential_discrepancies: List[str] = Field(default_factory=list)
    missing_documents: List[str] = Field(default_factory=list)
    illustrative_financials: Dict[str, Any] = Field(default_factory=dict)
    recommended_next_steps: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    human_review_required: bool = True
    disclaimer: str = (
        "This report is an investigative aid only. It does not approve, deny, "
        "settle, or pay any claim. Final decisions require licensed human review. "
        "Policy-date checks and coverage flags alone do not establish legal coverage."
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_report(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        raw_evidence = normalize_retrieved_evidence(data.get("retrieved_evidence"))
        data["retrieved_evidence"] = [coerce_citation_dict(x) for x in raw_evidence]

        for key in (
            "coverage_considerations",
            "potential_discrepancies",
            "missing_documents",
            "recommended_next_steps",
            "unresolved_questions",
        ):
            data[key] = _as_str_list(data.get(key))

        for key in ("policy_facts", "estimate_analysis", "illustrative_financials"):
            val = data.get(key)
            if val is None:
                data[key] = {}
            elif not isinstance(val, dict):
                data[key] = {"value": val}

        if not data.get("claim_summary"):
            data["claim_summary"] = f"Investigation summary for {data.get('claim_id', 'unknown')}"
        if not data.get("investigation_status"):
            data["investigation_status"] = "pending_human_review"
        return data


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                out.append(json.dumps(item, default=str)[:300])
            else:
                out.append(str(item))
        return out
    return [str(value)]


class InvestigateRequest(BaseModel):
    claim_id: Optional[str] = None
    question: str = (
        "Investigate this claim: validate policy dates, check coverage facts, "
        "analyze the repair estimate, identify missing documents, retrieve "
        "relevant policy clauses, and produce an investigation report."
    )


class InvestigateResponse(BaseModel):
    run_id: str
    claim_id: str = "portfolio"
    status: str
    stream_url: str
