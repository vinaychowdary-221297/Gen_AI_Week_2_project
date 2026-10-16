from decimal import Decimal

from app.agent.tools import (
    analyze_repair_estimate,
    check_coverage_facts,
    check_missing_documents,
    find_similar_claims,
    get_claim_details,
    validate_policy_dates,
)


def test_clm1001_claim_details():
    details = get_claim_details("CLM-1001")
    assert details["policy_id"] == "POL-5001"
    assert details["vehicle"]["make"] == "Toyota"
    assert details["vehicle"]["model"] == "RAV4"
    assert details["accident_date"] == "2026-08-15"


def test_policy_dates_active():
    result = validate_policy_dates("POL-5001", "2026-08-15")
    assert result["loss_date_within_period"] is True


def test_policy_dates_expired_claim():
    result = validate_policy_dates("POL-5004", "2026-03-10")
    assert result["loss_date_within_period"] is False


def test_coverage_facts_collision_listed():
    facts = check_coverage_facts("CLM-1001")
    assert facts["collision_listed"] is True
    assert facts["collision_deductible"] == 500.0
    assert "listed" in facts["collision_status"].lower()
    assert "Collision" in facts["summary"]


def test_eq02_collision_listed_language():
    """EQ-02 gold: collision coverage is listed for CLM-1001."""
    facts = check_coverage_facts("CLM-1001")
    assert facts["collision_listed"] is True
    blob = (facts["summary"] + " " + facts["collision_status"]).lower()
    assert "collision" in blob and "listed" in blob
    assert "not listed" not in facts["collision_status"].lower()


def test_report_accepts_malformed_tool_evidence():
    """LLM often puts tool stubs into retrieved_evidence — must not crash."""
    from app.agent.tools import generate_investigation_report
    from app.data.models import InvestigationReport

    evidence = [
        {
            "type": "policy_date_validation",
            "tool": "validate_policy_dates",
            "loss_date_within_period": True,
            "loss_date": "2026-08-15",
            "effective_date": "2026-01-01",
            "expiration_date": "2027-01-01",
        },
        {
            "type": "coverage_facts",
            "tool": "check_coverage_facts",
            "collision_status": "Collision coverage is listed on the policy.",
        },
        {
            "document_name": "POL-5001.md",
            "section": "Section 3",
            "excerpt": "If Collision is listed in the Declarations...",
        },
        {
            "type": "policy_document",
            "text": "Collision means the upset of your covered auto or its impact with another vehicle or object.",
        },
        {
            "type": "policy_document",
            "content": "We will pay minus the applicable Collision deductible.",
        },
        {
            "type": "repair_estimate",
            "submitted_total": 5320.5,
            "after_deductible": 4320.5,
        },
        {
            "type": "missing_documents",
            "missing_documents": ["Proof of Ownership"],
        },
        {
            "source": "POL-5004.md",
            "section": "Personal Auto Policy POL-5004",
        },
    ]
    report = generate_investigation_report(
        claim_id="CLM-1001",
        claim_summary="Test summary",
        retrieved_evidence=evidence,
    )
    assert report["claim_id"] == "CLM-1001"
    assert report.get("report_builder") == "v5_plain_dict"
    assert len(report["retrieved_evidence"]) >= 4
    assert all("document_name" in c and "excerpt" in c for c in report["retrieved_evidence"])

    # Even Pydantic InvestigationReport must accept these LLM shapes
    validated = InvestigationReport.model_validate(
        {"claim_id": "CLM-1001", "claim_summary": "t", "retrieved_evidence": evidence}
    )
    assert len(validated.retrieved_evidence) >= 4
    assert all(c.get("document_name") and "excerpt" in c for c in validated.retrieved_evidence)


def test_coverage_facts_no_collision():
    facts = check_coverage_facts("CLM-1002")
    assert facts["collision_listed"] is False


def test_estimate_uses_decimal_and_flags_duplicates():
    analysis = analyze_repair_estimate("CLM-1005")
    assert "illustrative_net_amount" in analysis
    assert isinstance(analysis["submitted_total"], float)
    assert len(analysis["potential_duplicate_charges"]) >= 1
    # Net = total - deductible (not LLM arithmetic)
    assert analysis["illustrative_net_amount"] == round(
        analysis["submitted_total"] - analysis["illustrative_deductible_applied"], 2
    )


def test_clm1001_estimate_net():
    analysis = analyze_repair_estimate("CLM-1001")
    expected_net = round(4820.50 - 500.0, 2)
    assert analysis["illustrative_net_amount"] == expected_net


def test_missing_documents():
    missing = check_missing_documents("CLM-1002")
    assert "missing_documents" in missing
    assert isinstance(missing["missing_documents"], list)


def test_similar_claims():
    similar = find_similar_claims("CLM-1001")
    assert similar["claim_id"] == "CLM-1001"
    assert len(similar["similar_claims"]) > 0
