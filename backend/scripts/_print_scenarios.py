import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent / "data"
claims = json.loads((root / "claims.json").read_text(encoding="utf-8"))
policies = {p["policy_id"]: p for p in json.loads((root / "policies.json").read_text(encoding="utf-8"))}
for c in claims:
    p = policies[c["policy_id"]]
    print("---")
    print(c["claim_id"], c.get("scenario_tag"))
    print("policy", c["policy_id"], p["status"], p["effective_date"], "->", p["expiration_date"])
    print("coverages", ", ".join(p["coverages"]))
    print("collision_ded", p["collision_deductible"], "comp_ded", p["comprehensive_deductible"])
    print("loss", c["accident_date"], "|", c["accident_description"][:100])
    print("docs", c["submitted_documents"])
    print("estimate", c["estimate_total"])
