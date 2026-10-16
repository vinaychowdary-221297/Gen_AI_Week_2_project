from app.rag.rrf import reciprocal_rank_fusion


def test_rrf_basic_fusion_and_dedup():
    list_a = [
        {"chunk_id": "a", "score": 10},
        {"chunk_id": "b", "score": 9},
        {"chunk_id": "c", "score": 8},
    ]
    list_b = [
        {"chunk_id": "b", "score": 0.9},
        {"chunk_id": "d", "score": 0.8},
        {"chunk_id": "a", "score": 0.7},
    ]
    fused = reciprocal_rank_fusion([list_a, list_b], k=60, top_k=4)
    ids = [x["chunk_id"] for x in fused]
    assert ids[0] in {"a", "b"}  # appear in both lists → highest RRF
    assert len(ids) == len(set(ids))
    assert "rrf_score" in fused[0]
    # b and a should outrank unique c/d
    assert set(ids[:2]) == {"a", "b"}


def test_rrf_formula():
    only = [[{"chunk_id": "x"}, {"chunk_id": "y"}]]
    fused = reciprocal_rank_fusion(only, k=60, top_k=2)
    assert abs(fused[0]["rrf_score"] - (1 / 61)) < 1e-9
    assert abs(fused[1]["rrf_score"] - (1 / 62)) < 1e-9
