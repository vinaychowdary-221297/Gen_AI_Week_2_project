"""Claim estimate documents: preliminary vs facility parse + compare helpers."""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import CLAIMS_DIR, DATA_DIR
from app.data.loader import get_claim, get_line_items, get_policy


def _money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def claim_docs_dir(claim_id: str) -> Path:
    return CLAIMS_DIR / claim_id


def estimate_path(claim_id: str, estimate_type: str = "facility") -> Path:
    name = (
        "Preliminary_Estimate.md"
        if estimate_type.lower() in {"preliminary", "prelim", "desk"}
        else "Repair_Facility_Estimate.md"
    )
    return claim_docs_dir(claim_id) / name


def list_claim_files(claim_id: str) -> List[Dict[str, Any]]:
    root = claim_docs_dir(claim_id)
    files: List[Dict[str, Any]] = []
    if not root.exists():
        return files
    for path in sorted(root.iterdir()):
        if path.is_file():
            files.append(
                {
                    "filename": path.name,
                    "path": str(path.relative_to(DATA_DIR)),
                    "bytes": path.stat().st_size,
                }
            )
    return files


_LINE_RE = re.compile(
    r"^\|\s*(?P<desc>[^|]+?)\s*\|\s*(?P<part>[^|]*?)\s*\|\s*"
    r"(?P<hours>[\d.]+)\s*\|\s*(?P<rate>[\d.]+)\s*\|\s*"
    r"(?P<parts>[\d.]+)\s*\|\s*(?P<total>[\d.]+)\s*\|",
    re.MULTILINE,
)
_TOTAL_RE = re.compile(r"Grand Total[:\s]*\$?\s*([\d,]+\.?\d*)", re.IGNORECASE)


def parse_estimate_markdown(text: str) -> Dict[str, Any]:
    lines: List[Dict[str, Any]] = []
    for m in _LINE_RE.finditer(text):
        desc = m.group("desc").strip()
        if desc.lower() in {"description", "---"} or desc.startswith("-"):
            continue
        hours = float(m.group("hours"))
        rate = float(m.group("rate"))
        parts = float(m.group("parts"))
        total = float(m.group("total"))
        lines.append(
            {
                "description": desc,
                "part_number": m.group("part").strip() or None,
                "labor_hours": hours,
                "labor_rate": rate,
                "parts_cost": parts,
                "total": total,
            }
        )
    grand = None
    tm = _TOTAL_RE.search(text)
    if tm:
        grand = float(tm.group(1).replace(",", ""))
    elif lines:
        grand = float(sum(_money(x["total"]) for x in lines))
    return {"line_items": lines, "grand_total": grand, "raw_chars": len(text)}


def load_estimate_document(
    claim_id: str, estimate_type: str = "facility"
) -> Dict[str, Any]:
    path = estimate_path(claim_id, estimate_type)
    if not path.exists():
        # Fallback: synthesize from JSON line items for facility
        if estimate_type.lower() not in {"preliminary", "prelim", "desk"}:
            items = get_line_items(claim_id)
            line_items = [i.model_dump() for i in items]
            total = sum((_money(i.get("total") or 0) for i in line_items), Decimal("0.00"))
            return {
                "claim_id": claim_id,
                "estimate_type": "facility",
                "source": "repair_line_items.json",
                "path": None,
                "line_items": line_items,
                "grand_total": float(total),
                "note": "Markdown estimate missing; used JSON line items fallback.",
            }
        return {
            "claim_id": claim_id,
            "estimate_type": "preliminary",
            "source": None,
            "path": None,
            "line_items": [],
            "grand_total": None,
            "error": f"Missing file: {path.name}. Run generate_data.py.",
        }
    text = path.read_text(encoding="utf-8")
    parsed = parse_estimate_markdown(text)
    return {
        "claim_id": claim_id,
        "estimate_type": (
            "preliminary"
            if estimate_type.lower() in {"preliminary", "prelim", "desk"}
            else "facility"
        ),
        "source": path.name,
        "path": str(path.relative_to(DATA_DIR)),
        "line_items": parsed["line_items"],
        "grand_total": parsed["grand_total"],
        "excerpt": text[:400],
    }


def build_preliminary_from_claim(claim_id: str) -> Dict[str, Any]:
    """Desk-style preliminary from claim facts (no web). Used when MD missing or as base."""
    claim = get_claim(claim_id)
    policy = get_policy(claim.policy_id)
    v = claim.vehicle
    # Rough illustrative desk lines from scenario
    tag = (claim.scenario_tag or "").lower()
    if "hail" in tag:
        rows = [
            ("Hood panel blend", "HD-10", 2.0, 85.0, 0.0),
            ("Roof repair labor", "RF-01", 3.0, 85.0, 0.0),
            ("Paint materials", "PM-01", 0.0, 0.0, 180.0),
        ]
    elif "glass" in tag:
        rows = [("Windshield OEM", "GL-01", 2.0, 95.0, 480.0)]
    else:
        rows = [
            ("Rear bumper cover", "RB-100", 2.0, 85.0, 350.0),
            ("Labor - body", "LB-01", 3.0, 85.0, 0.0),
            ("Paint materials", "PM-01", 0.0, 0.0, 200.0),
        ]
    line_items = []
    total = Decimal("0.00")
    for desc, part, hours, rate, parts in rows:
        line_total = _money(Decimal(str(hours)) * Decimal(str(rate)) + Decimal(str(parts)))
        total += line_total
        line_items.append(
            {
                "description": desc,
                "part_number": part,
                "labor_hours": hours,
                "labor_rate": rate,
                "parts_cost": parts,
                "total": float(line_total),
            }
        )
    return {
        "claim_id": claim_id,
        "estimate_type": "preliminary",
        "source": "desk_rules_from_claim_facts",
        "vehicle": f"{v.year} {v.make} {v.model}",
        "location": claim.location,
        "line_items": line_items,
        "grand_total": float(total),
        "deductible_hint": {
            "collision": policy.collision_deductible,
            "comprehensive": policy.comprehensive_deductible,
        },
        "disclaimer": (
            "Preliminary estimate based on information on file (FNOL / photos / scenario). "
            "Amounts are illustrative and may change after the vehicle is inspected at a "
            "repair facility. Not a settlement offer."
        ),
    }


def compare_estimates(
    preliminary: Dict[str, Any], facility: Dict[str, Any]
) -> Dict[str, Any]:
    p_total = preliminary.get("grand_total")
    f_total = facility.get("grand_total")
    delta = None
    pct = None
    if p_total is not None and f_total is not None:
        delta = float(_money(f_total) - _money(p_total))
        if float(p_total) > 0:
            pct = round(100.0 * delta / float(p_total), 1)
    p_descs = {str(x.get("description", "")).lower() for x in preliminary.get("line_items") or []}
    new_lines = [
        x.get("description")
        for x in facility.get("line_items") or []
        if str(x.get("description", "")).lower() not in p_descs
    ]
    return {
        "preliminary_total": p_total,
        "facility_total": f_total,
        "delta_facility_minus_preliminary": delta,
        "percent_change": pct,
        "new_lines_after_facility": new_lines,
        "message": (
            "Estimate changed after vehicle moved to repair facility (tear-down / shop supplement)."
            if delta and abs(delta) > 1
            else "Preliminary and facility totals are similar or one version is missing."
        ),
        "disclaimer": (
            "Version comparison is investigative only. Supplements require human adjuster review. "
            "Do not approve, deny, settle, or pay from these figures alone."
        ),
    }


def format_estimate_markdown(
    *,
    claim_id: str,
    title: str,
    shop_name: str,
    vehicle: str,
    vin: str,
    location: str,
    line_items: List[Dict[str, Any]],
    note: str,
) -> str:
    rows = [
        "| Description | Part | Hours | Rate | Parts | Total |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    grand = Decimal("0.00")
    for item in line_items:
        total = _money(item.get("total", 0))
        grand += total
        rows.append(
            f"| {item.get('description')} | {item.get('part_number') or ''} | "
            f"{item.get('labor_hours', 0)} | {item.get('labor_rate', 0)} | "
            f"{item.get('parts_cost', 0)} | {float(total):.2f} |"
        )
    body = "\n".join(rows)
    return (
        f"# {title}\n\n"
        f"**Claim:** {claim_id}  \n"
        f"**Shop / source:** {shop_name}  \n"
        f"**Vehicle:** {vehicle}  \n"
        f"**VIN:** {vin}  \n"
        f"**Location:** {location}  \n\n"
        f"{body}\n\n"
        f"**Grand Total:** ${float(grand):.2f}\n\n"
        f"_{note}_\n"
    )
