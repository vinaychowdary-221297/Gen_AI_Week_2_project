from pathlib import Path

from app.rag.chunking import chunk_document, chunk_text


def test_chunk_overlap():
    words = " ".join(f"w{i}" for i in range(100))
    chunks = chunk_text(words, chunk_size=20, overlap=5)
    assert len(chunks) >= 5
    assert chunks[0].startswith("w0")


def test_policy_markdown_chunking():
    path = Path(__file__).resolve().parent.parent / "data" / "policies" / "POL-5001.md"
    chunks = chunk_document(
        path,
        policy_id="POL-5001",
        jurisdiction="TX",
        policy_form_version="PAP-TX-2025.1",
        effective_date="2026-01-01",
        expiration_date="2027-01-01",
    )
    assert len(chunks) >= 3
    assert all(c.page_number is None for c in chunks)  # markdown has no pages
    assert all(c.policy_id == "POL-5001" for c in chunks)
    assert any("Collision" in c.chunk_text or "collision" in c.chunk_text.lower() for c in chunks)
