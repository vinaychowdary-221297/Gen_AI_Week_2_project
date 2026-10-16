"""Generate synthetic insurance policies, claims, estimates, and evaluation set.

Uses a fixed random seed for reproducibility.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

SEED = 42
ROOT = Path(__file__).resolve().parent.parent / "data"
POLICIES_DIR = ROOT / "policies"
CLAIMS_DIR = ROOT / "claims"


def ensure_dirs() -> None:
    POLICIES_DIR.mkdir(parents=True, exist_ok=True)
    CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def policy_markdown(policy: dict) -> str:
    coverages = ", ".join(policy["coverages"])
    endorsements = ", ".join(policy["endorsements"]) or "None"
    v = policy["vehicle"]
    return f"""# Personal Auto Policy {policy['policy_id']}

**Form Version:** {policy['policy_form_version']}  
**Jurisdiction:** {policy['jurisdiction']}  
**Named Insured:** {policy['insured_name']}  
**Effective Date:** {policy['effective_date']}  
**Expiration Date:** {policy['expiration_date']}  
**Status:** {policy['status']}

## Section 1 — Declarations

This policy covers the following vehicle:

- Year/Make/Model: {v['year']} {v['make']} {v['model']} {v.get('trim') or ''}
- VIN: {v.get('vin') or 'N/A'}
- Color: {v.get('color') or 'N/A'}

Listed coverages: {coverages}.

Collision deductible: ${policy['collision_deductible']:.2f}  
Comprehensive deductible: ${policy['comprehensive_deductible']:.2f}  
Bodily injury liability limit: ${policy['liability_limit_bodily']:,} per person  
Property damage liability limit: ${policy['liability_limit_property']:,} per accident

Endorsements: {endorsements}.

## Section 2 — Definitions

**Collision** means the upset of your covered auto or its impact with another vehicle or object.

**Comprehensive** means loss caused by other than collision, including fire, theft, vandalism, flood, and glass breakage.

**Deductible** means the amount you must pay before the insurer pays for a covered loss under Collision or Comprehensive.

**Period of coverage** means the time between the Effective Date and Expiration Date shown in the Declarations, inclusive of both dates unless cancelled earlier.

## Section 3 — Collision Coverage

If Collision is listed in the Declarations, we will pay for direct and accidental loss to your covered auto caused by collision, minus the applicable Collision deductible.

Payment is limited to the lesser of:

1. Actual cash value of the damaged property; or
2. The amount necessary to repair or replace the property with other property of like kind and quality.

Illustrative net repair amount = submitted repair total − applicable deductible, subject to human review of duplicates, betterment, and unrelated damage.

## Section 4 — Comprehensive Coverage

If Comprehensive is listed, we pay for loss other than collision, minus the Comprehensive deductible.

## Section 5 — Liability Coverage

We pay damages for bodily injury or property damage for which an insured becomes legally responsible because of an auto accident, subject to the limits shown in the Declarations.

## Section 6 — Exclusions

We do not provide coverage for:

1. **Intentional acts** — damage expected or intended by an insured.
2. **Racing** — use of the auto in any prearranged or organized racing, speed contest, or stunting activity.
3. **Business use of personal auto** — carrying persons or property for a fee, unless rideshare endorsement END-RS-01 is listed.
4. **Wear and tear** — mechanical breakdown, road damage to tires, and ordinary wear.
5. **War / nuclear hazard**.
6. **Regular use of non-owned auto** not listed on the policy.
7. **Aftermarket performance modifications** that materially increase risk unless disclosed and endorsed.
8. **Fraud or material misrepresentation** in the claim or application.

## Section 7 — Duties After an Accident or Loss

You must:

1. Promptly notify us of the accident date, location, and description.
2. Cooperate with investigation and settlement.
3. Submit a police report when required by law or when another party is involved.
4. Protect the vehicle from further damage.
5. Allow inspection before permanent repairs when reasonably requested.
6. Provide repair estimates, photos, and ownership proof upon request.

Failure to comply may delay investigation; it does not automatically void coverage without human legal review.

## Section 8 — Endorsements

### END-RS-01 Rideshare Use (if listed)

Extends liability and physical damage while the insured vehicle is logged into a transportation network platform in a waiting period, subject to platform primary coverage rules.

### END-GL-02 OEM Glass (if listed)

Glass repairs use OEM parts when available.

### END-RR-03 Rental Reimbursement (if listed)

Pays reasonable rental costs while the covered auto is withdrawn from use due to a covered loss, up to declared daily/aggregate limits.

## Section 9 — Claim Investigation Notes for Adjusters

Policy-date checks confirm only whether the reported loss date falls within the Declarations period. Coverage flags confirm only whether a coverage type is listed. Neither alone establishes legal coverage, causation, or entitlement to payment. All outcomes require human review.
"""


def build_policies() -> list:
    policies = [
        {
            "policy_id": "POL-5001",
            "insured_name": "Avery Chen",
            "jurisdiction": "TX",
            "effective_date": "2026-01-01",
            "expiration_date": "2027-01-01",
            "policy_form_version": "PAP-TX-2025.1",
            "coverages": ["Liability", "Collision", "Comprehensive", "Uninsured Motorist"],
            "collision_deductible": 500.0,
            "comprehensive_deductible": 250.0,
            "liability_limit_bodily": 100000,
            "liability_limit_property": 50000,
            "vehicle": {
                "year": 2024,
                "make": "Toyota",
                "model": "RAV4",
                "trim": "XSE",
                "vin": "JTMB1RFV0R4123456",
                "color": "Blueprint",
            },
            "endorsements": ["END-RR-03"],
            "status": "active",
        },
        {
            "policy_id": "POL-5002",
            "insured_name": "Jordan Blake",
            "jurisdiction": "CA",
            "effective_date": "2025-06-15",
            "expiration_date": "2026-06-15",
            "policy_form_version": "PAP-CA-2025.2",
            "coverages": ["Liability", "Comprehensive"],
            "collision_deductible": 1000.0,
            "comprehensive_deductible": 500.0,
            "liability_limit_bodily": 50000,
            "liability_limit_property": 25000,
            "vehicle": {
                "year": 2021,
                "make": "Honda",
                "model": "Civic",
                "trim": "EX",
                "vin": "19XFC2F59ME123456",
                "color": "Sonic Gray",
            },
            "endorsements": [],
            "status": "active",
        },
        {
            "policy_id": "POL-5003",
            "insured_name": "Samira Ortiz",
            "jurisdiction": "FL",
            "effective_date": "2026-03-01",
            "expiration_date": "2027-03-01",
            "policy_form_version": "PAP-FL-2025.1",
            "coverages": ["Liability", "Collision", "Comprehensive", "PIP"],
            "collision_deductible": 750.0,
            "comprehensive_deductible": 500.0,
            "liability_limit_bodily": 100000,
            "liability_limit_property": 50000,
            "vehicle": {
                "year": 2023,
                "make": "Ford",
                "model": "Escape",
                "trim": "SE",
                "vin": "1FMCU9G60PUA12345",
                "color": "Oxford White",
            },
            "endorsements": ["END-GL-02"],
            "status": "active",
        },
        {
            "policy_id": "POL-5004",
            "insured_name": "Morgan Ellis",
            "jurisdiction": "NY",
            "effective_date": "2025-01-01",
            "expiration_date": "2026-01-01",
            "policy_form_version": "PAP-NY-2024.4",
            "coverages": ["Liability", "Collision", "Comprehensive"],
            "collision_deductible": 500.0,
            "comprehensive_deductible": 250.0,
            "liability_limit_bodily": 100000,
            "liability_limit_property": 50000,
            "vehicle": {
                "year": 2022,
                "make": "Subaru",
                "model": "Outback",
                "trim": "Premium",
                "vin": "4S4BTACC2N3123456",
                "color": "Crystal White",
            },
            "endorsements": ["END-RS-01"],
            "status": "expired",
        },
        {
            "policy_id": "POL-5005",
            "insured_name": "Riley Nguyen",
            "jurisdiction": "IL",
            "effective_date": "2026-02-01",
            "expiration_date": "2027-02-01",
            "policy_form_version": "PAP-IL-2025.1",
            "coverages": ["Liability", "Collision", "Comprehensive", "Roadside"],
            "collision_deductible": 1000.0,
            "comprehensive_deductible": 500.0,
            "liability_limit_bodily": 250000,
            "liability_limit_property": 100000,
            "vehicle": {
                "year": 2025,
                "make": "Tesla",
                "model": "Model Y",
                "trim": "Long Range",
                "vin": "7SAYGDEE1PF123456",
                "color": "Midnight Silver",
            },
            "endorsements": ["END-RR-03", "END-GL-02"],
            "status": "active",
        },
    ]
    return policies


def build_claims(policies: list) -> list:
    by_id = {p["policy_id"]: p for p in policies}
    claims = [
        {
            "claim_id": "CLM-1001",
            "policy_id": "POL-5001",
            "accident_date": "2026-08-15",
            "accident_description": (
                "Insured was stopped at a red light on Highway 183 when another vehicle "
                "rear-ended the 2024 Toyota RAV4 XSE. Rear bumper, hatch, and exhaust tip damaged. "
                "Airbags did not deploy. No injuries reported."
            ),
            "claim_status": "under_investigation",
            "vehicle": by_id["POL-5001"]["vehicle"],
            "reported_date": "2026-08-15",
            "location": "Austin, TX",
            "police_report_number": "APD-2026-081512",
            "submitted_documents": [
                "FNOL",
                "Police Report",
                "Repair Estimate",
                "Photos",
                "Driver License",
            ],
            "estimate_total": 4820.50,
            "scenario_tag": "standard_collision",
            "notes": "Demo scenario: active policy, collision listed, complete docs.",
        },
        {
            "claim_id": "CLM-1002",
            "policy_id": "POL-5002",
            "accident_date": "2026-04-02",
            "accident_description": "Side-swipe in parking garage damaging driver door and mirror.",
            "claim_status": "under_investigation",
            "vehicle": by_id["POL-5002"]["vehicle"],
            "reported_date": "2026-04-03",
            "location": "San Jose, CA",
            "police_report_number": None,
            "submitted_documents": ["FNOL", "Photos", "Repair Estimate"],
            "estimate_total": 2150.00,
            "scenario_tag": "no_collision_coverage",
            "notes": "Collision not listed on policy; comprehensive only.",
        },
        {
            "claim_id": "CLM-1003",
            "policy_id": "POL-5004",
            "accident_date": "2026-03-10",
            "accident_description": "Hit deer on rural road; front bumper and grille damage.",
            "claim_status": "under_investigation",
            "vehicle": by_id["POL-5004"]["vehicle"],
            "reported_date": "2026-03-11",
            "location": "Albany, NY",
            "police_report_number": "NYSP-44219",
            "submitted_documents": ["FNOL", "Police Report", "Repair Estimate"],
            "estimate_total": 3600.00,
            "scenario_tag": "policy_expired",
            "notes": "Loss date after policy expiration.",
        },
        {
            "claim_id": "CLM-1004",
            "policy_id": "POL-5003",
            "accident_date": "2026-07-01",
            "accident_description": "Hail storm damaged roof, hood, and trunk lid.",
            "claim_status": "under_investigation",
            "vehicle": by_id["POL-5003"]["vehicle"],
            "reported_date": "2026-07-02",
            "location": "Tampa, FL",
            "police_report_number": None,
            "submitted_documents": ["FNOL", "Photos", "Repair Estimate", "Weather Report"],
            "estimate_total": 5400.00,
            "scenario_tag": "comprehensive_hail",
            "notes": "Comprehensive claim; collision not implicated.",
        },
        {
            "claim_id": "CLM-1005",
            "policy_id": "POL-5005",
            "accident_date": "2026-09-05",
            "accident_description": "Rear-end collision on I-90; bumper and sensor suite damage.",
            "claim_status": "under_investigation",
            "vehicle": by_id["POL-5005"]["vehicle"],
            "reported_date": "2026-09-05",
            "location": "Chicago, IL",
            "police_report_number": "CPD-998211",
            "submitted_documents": ["FNOL", "Police Report", "Repair Estimate", "Photos"],
            "estimate_total": 8750.25,
            "scenario_tag": "duplicate_line_items",
            "notes": "Estimate contains potential duplicate ADAS calibration charge.",
        },
    ]

    # Fill remaining claims to reach 15
    templates = [
        ("CLM-1006", "POL-5001", "2026-05-20", "Minor parking lot ding on rear quarter panel.", "standard_collision"),
        ("CLM-1007", "POL-5001", "2026-06-12", "Glass crack from road debris on windshield.", "glass"),
        ("CLM-1008", "POL-5002", "2026-01-18", "Theft of catalytic converter overnight.", "comprehensive_theft"),
        ("CLM-1009", "POL-5003", "2026-08-22", "Flooding in underground garage soaked cabin floor.", "comprehensive_flood"),
        ("CLM-1010", "POL-5005", "2026-04-30", "Multi-car pileup; front and rear damage.", "standard_collision"),
        ("CLM-1011", "POL-5003", "2026-05-08", "Backing into pole at grocery store.", "standard_collision"),
        ("CLM-1012", "POL-5005", "2026-10-01", "Single-vehicle loss after hydroplaning.", "standard_collision"),
        ("CLM-1013", "POL-5002", "2025-12-01", "Vandalism scratches along passenger side.", "comprehensive_vandalism"),
        ("CLM-1014", "POL-5001", "2026-02-14", "Intersection T-bone at low speed; door and B-pillar.", "standard_collision"),
        ("CLM-1015", "POL-5004", "2025-11-20", "Historical claim while policy was active; used for similarity.", "historical"),
    ]
    for cid, pid, date, desc, tag in templates:
        p = by_id[pid]
        claims.append(
            {
                "claim_id": cid,
                "policy_id": pid,
                "accident_date": date,
                "accident_description": desc,
                "claim_status": "closed" if tag == "historical" else "under_investigation",
                "vehicle": p["vehicle"],
                "reported_date": date,
                "location": {
                    "POL-5001": "Austin, TX",
                    "POL-5002": "San Jose, CA",
                    "POL-5003": "Miami, FL",
                    "POL-5004": "Buffalo, NY",
                    "POL-5005": "Chicago, IL",
                }[pid],
                "police_report_number": None,
                "submitted_documents": ["FNOL", "Photos", "Repair Estimate"],
                "estimate_total": round(random.uniform(800, 7000), 2),
                "scenario_tag": tag,
                "notes": None,
            }
        )
    return claims


def build_documents(claims: list) -> list:
    required_types = [
        "FNOL",
        "Police Report",
        "Repair Estimate",
        "Photos",
        "Driver License",
        "Proof of Ownership",
        "Medical Authorization",
    ]
    docs = []
    doc_n = 1
    for claim in claims:
        submitted = set(claim["submitted_documents"])
        for dtype in required_types:
            if dtype in submitted or random.random() < 0.35:
                docs.append(
                    {
                        "document_id": f"DOC-{doc_n:04d}",
                        "claim_id": claim["claim_id"],
                        "document_type": dtype,
                        "filename": f"{claim['claim_id']}_{dtype.replace(' ', '_').lower()}.pdf",
                        "submitted": dtype in submitted,
                        "notes": None if dtype in submitted else "Not yet received",
                    }
                )
                doc_n += 1
    # Guarantee >= 30
    while len(docs) < 30:
        claim = random.choice(claims)
        docs.append(
            {
                "document_id": f"DOC-{doc_n:04d}",
                "claim_id": claim["claim_id"],
                "document_type": "Supplemental Photos",
                "filename": f"{claim['claim_id']}_supp_{doc_n}.jpg",
                "submitted": True,
                "notes": None,
            }
        )
        doc_n += 1
    return docs


def build_line_items(claims: list) -> list:
    catalog = [
        ("Rear bumper cover", "RB-100", 2.5, 85.0, 420.0),
        ("Rear bumper reinforcement", "RB-110", 1.5, 85.0, 180.0),
        ("Hatch panel blend", "HP-200", 3.0, 85.0, 0.0),
        ("Exhaust tip", "EX-55", 0.8, 85.0, 95.0),
        ("Paint materials", "PM-01", 0.0, 0.0, 275.0),
        ("ADAS calibration", "AD-90", 1.5, 140.0, 0.0),
        ("Front bumper cover", "FB-100", 2.8, 85.0, 390.0),
        ("Hood panel", "HD-10", 4.0, 85.0, 520.0),
        ("Windshield OEM", "GL-01", 2.0, 95.0, 480.0),
        ("Door shell", "DR-22", 5.0, 85.0, 650.0),
        ("Side mirror assembly", "MR-07", 1.0, 85.0, 210.0),
        ("Sensor suite module", "SS-33", 2.0, 140.0, 890.0),
        ("Labor - body", "LB-01", 6.0, 85.0, 0.0),
        ("Labor - paint", "LP-01", 5.0, 85.0, 0.0),
        ("Misc supplies", "MS-01", 0.0, 0.0, 65.0),
    ]
    items = []
    n = 1
    for claim in claims:
        count = random.randint(2, 5)
        chosen = random.sample(catalog, k=min(count, len(catalog)))
        # Special cases
        if claim["claim_id"] == "CLM-1001":
            chosen = catalog[:6]
        if claim["claim_id"] == "CLM-1005":
            chosen = [
                catalog[5],  # ADAS
                catalog[5],  # duplicate ADAS
                catalog[0],
                catalog[11],
                catalog[12],
                catalog[13],
            ]
        for desc, part, hours, rate, parts in chosen:
            labor = round(hours * rate, 2)
            total = round(labor + parts, 2)
            items.append(
                {
                    "line_id": f"LN-{n:04d}",
                    "claim_id": claim["claim_id"],
                    "description": desc,
                    "part_number": part,
                    "labor_hours": hours,
                    "labor_rate": rate,
                    "parts_cost": parts,
                    "total": total,
                }
            )
            n += 1
    while len(items) < 40:
        claim = random.choice(claims)
        desc, part, hours, rate, parts = random.choice(catalog)
        labor = round(hours * rate, 2)
        items.append(
            {
                "line_id": f"LN-{n:04d}",
                "claim_id": claim["claim_id"],
                "description": desc,
                "part_number": part,
                "labor_hours": hours,
                "labor_rate": rate,
                "parts_cost": parts,
                "total": round(labor + parts, 2),
            }
        )
        n += 1
    return items


def build_required_docs_checklist() -> dict:
    return {
        "collision": [
            "FNOL",
            "Police Report",
            "Repair Estimate",
            "Photos",
            "Driver License",
            "Proof of Ownership",
        ],
        "comprehensive": [
            "FNOL",
            "Repair Estimate",
            "Photos",
            "Driver License",
            "Proof of Ownership",
        ],
        "default": [
            "FNOL",
            "Repair Estimate",
            "Photos",
            "Driver License",
        ],
    }


def build_evaluation_questions() -> list:
    return [
        {
            "id": "EQ-01",
            "claim_id": "CLM-1001",
            "question": "Was the policy within its effective date range on the accident date?",
            "expected_contains": ["within", "effective", "2026-08-15"],
        },
        {
            "id": "EQ-02",
            "claim_id": "CLM-1001",
            "question": "Is collision coverage listed on the policy?",
            "expected_contains": ["Collision", "listed"],
        },
        {
            "id": "EQ-03",
            "claim_id": "CLM-1001",
            "question": "What is the collision deductible?",
            "expected_contains": ["500"],
        },
        {
            "id": "EQ-04",
            "claim_id": "CLM-1001",
            "question": "What is the illustrative net repair amount after deductible?",
            "expected_contains": ["deductible"],
        },
        {
            "id": "EQ-05",
            "claim_id": "CLM-1001",
            "question": "Are required documents missing?",
            "expected_contains": ["missing"],
        },
        {
            "id": "EQ-06",
            "claim_id": "CLM-1002",
            "question": "Is collision coverage listed?",
            "expected_contains": ["not listed", "Collision"],
        },
        {
            "id": "EQ-07",
            "claim_id": "CLM-1003",
            "question": "Was the policy active on the loss date?",
            "expected_contains": ["outside", "expir"],
        },
        {
            "id": "EQ-08",
            "claim_id": "CLM-1005",
            "question": "Are there potentially duplicate repair charges?",
            "expected_contains": ["duplicate", "ADAS"],
        },
        {
            "id": "EQ-09",
            "claim_id": "CLM-1004",
            "question": "Which coverage type may apply to hail damage?",
            "expected_contains": ["Comprehensive"],
        },
        {
            "id": "EQ-10",
            "claim_id": "CLM-1001",
            "question": "Which policy exclusions may be relevant to review?",
            "expected_contains": ["Exclusion"],
        },
        {
            "id": "EQ-11",
            "claim_id": "CLM-1001",
            "question": "What should the adjuster do next?",
            "expected_contains": ["human", "review"],
        },
        {
            "id": "EQ-12",
            "claim_id": "CLM-1005",
            "question": "What is the submitted repair estimate total?",
            "expected_contains": ["estimate"],
        },
        {
            "id": "EQ-13",
            "claim_id": "CLM-1002",
            "question": "Which documents are missing for this claim?",
            "expected_contains": ["missing"],
        },
        {
            "id": "EQ-14",
            "claim_id": "CLM-1001",
            "question": "Find similar historical claims and investigation patterns.",
            "expected_contains": ["similar"],
        },
        {
            "id": "EQ-15",
            "claim_id": "CLM-1001",
            "question": "Cite the collision coverage clause from the policy.",
            "expected_contains": ["Section 3", "Collision"],
        },
        {
            "id": "EQ-16",
            "claim_id": "CLM-1010",
            "question": "Validate policy dates for this multi-car claim.",
            "expected_contains": ["effective"],
        },
        {
            "id": "EQ-17",
            "claim_id": "CLM-1008",
            "question": "Check coverage facts for catalytic converter theft.",
            "expected_contains": ["Comprehensive"],
        },
        {
            "id": "EQ-18",
            "claim_id": "CLM-1001",
            "question": "What vehicle was involved in CLM-1001?",
            "expected_contains": ["RAV4"],
        },
        {
            "id": "EQ-19",
            "claim_id": "CLM-1003",
            "question": "List unresolved policy status questions.",
            "expected_contains": ["expir"],
        },
        {
            "id": "EQ-20",
            "claim_id": "CLM-1005",
            "question": "Produce a full investigation report for human review.",
            "expected_contains": ["human_review"],
        },
    ]


def write_clause_library() -> None:
    clauses = [
        {
            "clause_id": "CL-01",
            "title": "Collision definition",
            "section": "Section 2 — Definitions",
            "text": "Collision means the upset of your covered auto or its impact with another vehicle or object.",
        },
        {
            "clause_id": "CL-02",
            "title": "Comprehensive definition",
            "section": "Section 2 — Definitions",
            "text": "Comprehensive means loss caused by other than collision, including fire, theft, vandalism, flood, and glass breakage.",
        },
        {
            "clause_id": "CL-03",
            "title": "Collision payment",
            "section": "Section 3 — Collision Coverage",
            "text": "If Collision is listed in the Declarations, we will pay for direct and accidental loss to your covered auto caused by collision, minus the applicable Collision deductible.",
        },
        {
            "clause_id": "CL-04",
            "title": "Deductible definition",
            "section": "Section 2 — Definitions",
            "text": "Deductible means the amount you must pay before the insurer pays for a covered loss under Collision or Comprehensive.",
        },
        {
            "clause_id": "CL-05",
            "title": "Period of coverage",
            "section": "Section 2 — Definitions",
            "text": "Period of coverage means the time between the Effective Date and Expiration Date shown in the Declarations, inclusive of both dates unless cancelled earlier.",
        },
        {
            "clause_id": "CL-06",
            "title": "Intentional acts exclusion",
            "section": "Section 6 — Exclusions",
            "text": "We do not provide coverage for intentional acts — damage expected or intended by an insured.",
        },
        {
            "clause_id": "CL-07",
            "title": "Racing exclusion",
            "section": "Section 6 — Exclusions",
            "text": "We do not provide coverage for racing — use of the auto in any prearranged or organized racing, speed contest, or stunting activity.",
        },
        {
            "clause_id": "CL-08",
            "title": "Business use exclusion",
            "section": "Section 6 — Exclusions",
            "text": "We do not provide coverage for business use of personal auto — carrying persons or property for a fee, unless rideshare endorsement END-RS-01 is listed.",
        },
        {
            "clause_id": "CL-09",
            "title": "Wear and tear exclusion",
            "section": "Section 6 — Exclusions",
            "text": "We do not provide coverage for wear and tear — mechanical breakdown, road damage to tires, and ordinary wear.",
        },
        {
            "clause_id": "CL-10",
            "title": "Duties after loss",
            "section": "Section 7 — Duties After an Accident or Loss",
            "text": "You must promptly notify us, cooperate with investigation, submit a police report when required, protect the vehicle, allow inspection, and provide estimates and photos.",
        },
        {
            "clause_id": "CL-11",
            "title": "Rideshare endorsement",
            "section": "Section 8 — Endorsements",
            "text": "END-RS-01 extends liability and physical damage while the insured vehicle is logged into a transportation network platform in a waiting period.",
        },
        {
            "clause_id": "CL-12",
            "title": "Human review requirement",
            "section": "Section 9 — Claim Investigation Notes for Adjusters",
            "text": "Policy-date checks and coverage flags alone do not establish legal coverage. All outcomes require human review.",
        },
    ]
    write_json(ROOT / "policy_clauses.json", clauses)


def main() -> None:
    random.seed(SEED)
    ensure_dirs()
    policies = build_policies()
    claims = build_claims(policies)
    documents = build_documents(claims)
    line_items = build_line_items(claims)
    checklist = build_required_docs_checklist()
    eval_qs = build_evaluation_questions()

    write_json(ROOT / "policies.json", policies)
    write_json(ROOT / "claims.json", claims)
    write_json(ROOT / "claim_documents.json", documents)
    write_json(ROOT / "repair_line_items.json", line_items)
    write_json(ROOT / "required_documents.json", checklist)
    write_json(ROOT / "evaluation_questions.json", eval_qs)
    write_clause_library()

    for p in policies:
        path = POLICIES_DIR / f"{p['policy_id']}.md"
        path.write_text(policy_markdown(p), encoding="utf-8")

    # CSV export for line items
    csv_path = ROOT / "repair_line_items.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "line_id",
                "claim_id",
                "description",
                "part_number",
                "labor_hours",
                "labor_rate",
                "parts_cost",
                "total",
            ],
        )
        writer.writeheader()
        writer.writerows(line_items)

    print("Generated synthetic dataset:")
    print(f"  policies: {len(policies)}")
    print(f"  claims: {len(claims)}")
    print(f"  documents: {len(documents)}")
    print(f"  line items: {len(line_items)}")
    print(f"  evaluation questions: {len(eval_qs)}")
    print(f"  policy markdown files: {len(list(POLICIES_DIR.glob('*.md')))}")


if __name__ == "__main__":
    main()
