"""Week 3 tools: classify, estimate docs, handoff (no live Keenable)."""

from __future__ import annotations

from app.agent.estimate_docs import compare_estimates, parse_estimate_markdown
from app.agent.week3_tools import (
    classify_claim,
    compare_estimate_versions,
    list_claim_documents,
    parse_repair_estimate_document,
    request_human_handoff,
)


def test_classify_claim_scenarios():
    c1 = classify_claim("CLM-1001")
    assert c1["loss_type"] == "collision"
    assert c1["recommended_track"] == "standard"

    c2 = classify_claim("CLM-1002")
    assert "coverage_gap" in c2["recommended_track"] or "collision" in c2["flags"][0]

    c3 = classify_claim("CLM-1003")
    assert c3["auto_escalate_to_human"] is True
    assert c3["recommended_track"] == "expired_policy"

    c4 = classify_claim("CLM-1004")
    assert c4["loss_type"] == "comprehensive"

    c5 = classify_claim("CLM-1005")
    assert c5["recommended_track"] == "duplicate_review"


def test_parse_estimate_markdown_table():
    md = """
# Test
| Description | Part | Hours | Rate | Parts | Total |
| --- | --- | --- | --- | --- | --- |
| Rear bumper cover | RB-100 | 2.0 | 85.0 | 420.0 | 590.0 |
| ADAS calibration | AD-90 | 1.5 | 140.0 | 0.0 | 210.0 |

**Grand Total:** $800.00
"""
    parsed = parse_estimate_markdown(md)
    assert len(parsed["line_items"]) == 2
    assert parsed["grand_total"] == 800.0


def test_parse_facility_document_clm1001():
    doc = parse_repair_estimate_document("CLM-1001", estimate_type="facility")
    assert doc.get("line_items")
    assert doc.get("grand_total") is not None


def test_compare_estimate_versions_clm1001():
    result = compare_estimate_versions("CLM-1001")
    assert "comparison" in result
    assert result["comparison"]["disclaimer"]


def test_list_claim_documents():
    docs = list_claim_documents("CLM-1001")
    assert docs["claim_id"] == "CLM-1001"
    assert "required_checklist" in docs


def test_request_human_handoff():
    h = request_human_handoff(
        reason="Keenable unavailable",
        blocking_questions=["Retry web research?"],
        claim_id="CLM-1001",
    )
    assert h["handoff_requested"] is True
    assert h["human_review_required"] is True
    assert h["status"] == "awaiting_human"


def test_compare_estimates_delta():
    prelim = {"grand_total": 1000.0, "line_items": [{"description": "A"}]}
    facility = {
        "grand_total": 1500.0,
        "line_items": [{"description": "A"}, {"description": "B"}],
    }
    cmp = compare_estimates(prelim, facility)
    assert cmp["delta_facility_minus_preliminary"] == 500.0
    assert "B" in cmp["new_lines_after_facility"]
