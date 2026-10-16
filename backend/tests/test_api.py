from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    res = client.get("/")
    assert res.status_code == 200
    assert "Claims" in res.json()["name"]


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["backend"]["ok"] is True


def test_list_claims():
    res = client.get("/api/claims")
    assert res.status_code == 200
    claims = res.json()
    assert len(claims) == 15
    assert any(c["claim_id"] == "CLM-1001" for c in claims)


def test_claim_detail():
    res = client.get("/api/claims/CLM-1001")
    assert res.status_code == 200
    body = res.json()
    assert body["vehicle"]["model"] == "RAV4"
    assert body["accident_date"] == "2026-08-15"


def test_workflow_nodes():
    res = client.get("/api/workflow/nodes")
    assert res.status_code == 200
    nodes = res.json()
    ids = {n["id"] for n in nodes}
    assert "langgraph_agent" in ids
    assert "pinecone_search" in ids
    assert "bm25_search" in ids
