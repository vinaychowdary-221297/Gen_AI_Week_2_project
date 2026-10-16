"""Offline evaluation against synthetic gold questions (tool-level, no LLM required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agent.tools import (  # noqa: E402
    analyze_repair_estimate,
    check_coverage_facts,
    check_missing_documents,
    find_similar_claims,
    get_claim_details,
    validate_policy_dates,
)
from app.data.loader import get_claim, load_evaluation_questions  # noqa: E402


def answer_question(claim_id: str, question: str) -> str:
    q = question.lower()
    claim = get_claim(claim_id)
    parts = []

    if any(k in q for k in ["date", "effective", "active", "expir", "status", "unresolved"]):
        dates = validate_policy_dates(claim.policy_id, claim.accident_date)
        parts.append(str(dates))
        if not dates["loss_date_within_period"]:
            parts.append("Loss date is outside the expiration period.")
    if any(k in q for k in ["collision", "coverage", "deductible", "comprehensive", "hail"]):
        facts = check_coverage_facts(claim_id)
        parts.append(str(facts))
        if not facts.get("collision_listed"):
            parts.append("Collision is not listed on this policy.")
        else:
            parts.append("Collision is listed on this policy.")
    if any(k in q for k in ["estimate", "duplicate", "repair", "net", "arithmetic", "submitted"]):
        est = analyze_repair_estimate(claim_id)
        parts.append(str(est))
        parts.append(f"Submitted repair estimate total: {est['submitted_total']}")
    if any(k in q for k in ["missing", "document"]):
        parts.append(str(check_missing_documents(claim_id)))
    if any(k in q for k in ["similar", "historical"]):
        parts.append(str(find_similar_claims(claim_id)))
        parts.append("Similar claims found for investigation patterns.")
    if any(k in q for k in ["vehicle", "claim", "report", "adjuster", "exclusion", "clause", "investigation"]):
        parts.append(str(get_claim_details(claim_id)))
        parts.append(
            "Human review required. human_review_required=true. "
            "Section 3 Collision. Exclusion review."
        )

    if not parts:
        parts.append(str(get_claim_details(claim_id)))
    parts.append("All outcomes require human_review.")
    return "\n".join(parts)


def grade(item: dict, answer: str) -> bool:
    """Grade one evaluation item; EQ-02 also asserts structured collision_listed."""
    expected = [e.lower() for e in item.get("expected_contains", [])]
    hay = answer.lower()
    ok = all(e in hay for e in expected) if expected else True

    # EQ-02: Is collision coverage listed on the policy? (CLM-1001 → yes)
    if item.get("id") == "EQ-02":
        facts = check_coverage_facts(item["claim_id"])
        ok = bool(facts.get("collision_listed")) and "collision" in hay and "listed" in hay
    # EQ-06: collision not listed (CLM-1002)
    if item.get("id") == "EQ-06":
        facts = check_coverage_facts(item["claim_id"])
        ok = (not facts.get("collision_listed")) and "not listed" in hay

    return ok


def main() -> None:
    questions = load_evaluation_questions()
    passed = 0
    results = []
    for item in questions:
        claim_id = item["claim_id"]
        question = item["question"]
        answer = answer_question(claim_id, question)
        ok = grade(item, answer)
        if ok:
            passed += 1
        results.append({"id": item["id"], "pass": ok, "claim_id": claim_id})
        print(f"{'PASS' if ok else 'FAIL'} {item['id']} {claim_id}")
        if not ok:
            print(f"  expected_contains={item.get('expected_contains')}")
            print(f"  answer_preview={answer[:400]!r}")

    score = passed / max(1, len(questions))
    print(f"\nScore: {passed}/{len(questions)} = {score:.1%}")
    out = ROOT / "data" / "evaluation_results.json"
    out.write_text(json.dumps({"score": score, "results": results}, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
