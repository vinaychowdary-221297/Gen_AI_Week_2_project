"""Load synthetic claims datasets from local JSON/CSV files."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import DATA_DIR, POLICIES_DIR
from app.data.models import ClaimDocument, ClaimRecord, PolicyRecord, RepairLineItem


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def load_policies() -> Dict[str, PolicyRecord]:
    raw = _read_json(DATA_DIR / "policies.json")
    return {p["policy_id"]: PolicyRecord.model_validate(p) for p in raw}


@lru_cache
def load_claims() -> Dict[str, ClaimRecord]:
    raw = _read_json(DATA_DIR / "claims.json")
    return {c["claim_id"]: ClaimRecord.model_validate(c) for c in raw}


@lru_cache
def load_documents() -> List[ClaimDocument]:
    raw = _read_json(DATA_DIR / "claim_documents.json")
    return [ClaimDocument.model_validate(d) for d in raw]


@lru_cache
def load_line_items() -> List[RepairLineItem]:
    raw = _read_json(DATA_DIR / "repair_line_items.json")
    return [RepairLineItem.model_validate(i) for i in raw]


@lru_cache
def load_required_docs() -> Dict[str, List[str]]:
    return _read_json(DATA_DIR / "required_documents.json")


@lru_cache
def load_evaluation_questions() -> List[Dict[str, Any]]:
    return _read_json(DATA_DIR / "evaluation_questions.json")


def clear_data_caches() -> None:
    """Drop JSON loaders so updated claims/line items are picked up without restart."""
    load_policies.cache_clear()
    load_claims.cache_clear()
    load_documents.cache_clear()
    load_line_items.cache_clear()
    load_required_docs.cache_clear()
    load_evaluation_questions.cache_clear()


def get_claim(claim_id: str) -> ClaimRecord:
    claims = load_claims()
    if claim_id not in claims:
        raise KeyError(f"Unknown claim_id: {claim_id}")
    return claims[claim_id]


def get_policy(policy_id: str) -> PolicyRecord:
    policies = load_policies()
    if policy_id not in policies:
        raise KeyError(f"Unknown policy_id: {policy_id}")
    return policies[policy_id]


def get_claim_documents(claim_id: str) -> List[ClaimDocument]:
    return [d for d in load_documents() if d.claim_id == claim_id]


def get_line_items(claim_id: str) -> List[RepairLineItem]:
    return [i for i in load_line_items() if i.claim_id == claim_id]


def list_policy_files() -> List[Path]:
    return sorted(POLICIES_DIR.glob("*.md")) + sorted(POLICIES_DIR.glob("*.txt"))


def claim_summary(claim_id: str) -> Dict[str, Any]:
    claim = get_claim(claim_id)
    policy = get_policy(claim.policy_id)
    return {
        "claim_id": claim.claim_id,
        "policy_id": claim.policy_id,
        "policy_number": claim.policy_id,
        "insured_name": policy.insured_name,
        "accident_date": claim.accident_date,
        "accident_description": claim.accident_description,
        "claim_status": claim.claim_status,
        "vehicle": claim.vehicle.model_dump(),
        "location": claim.location,
        "submitted_documents": claim.submitted_documents,
        "estimate_total": claim.estimate_total,
        "scenario_tag": claim.scenario_tag,
        "coverages": policy.coverages,
        "collision_deductible": policy.collision_deductible,
    }
