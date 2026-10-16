"""Ingest policy documents into BM25 + Pinecone."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass

from app.clients.nebius import get_nebius  # noqa: E402
from app.clients.pinecone_client import get_pinecone_store  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.data.loader import list_policy_files, load_policies  # noqa: E402
from app.rag.bm25_store import BM25Store  # noqa: E402
from app.rag.chunking import DocumentChunk, chunk_document  # noqa: E402


def main(reset_namespace: bool = True) -> None:
    settings = get_settings()
    settings.require_credentials()

    policies = load_policies()
    files = list_policy_files()
    if not files:
        raise SystemExit("No policy documents found. Run generate_data.py first.")

    all_chunks: list[DocumentChunk] = []
    for path in files:
        policy_id = path.stem
        policy = policies.get(policy_id)
        if not policy:
            print(f"Skipping {path.name}: no policy metadata")
            continue
        chunks = chunk_document(
            path,
            policy_id=policy.policy_id,
            jurisdiction=policy.jurisdiction,
            policy_form_version=policy.policy_form_version,
            effective_date=policy.effective_date,
            expiration_date=policy.expiration_date,
            document_type="policy",
        )
        print(f"{path.name}: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    if not all_chunks:
        raise SystemExit("No chunks produced.")

    # BM25
    bm25 = BM25Store()
    bm25.build(all_chunks)
    print(f"BM25 index built with {len(all_chunks)} chunks")

    # Embeddings + Pinecone
    nebius = get_nebius()
    dim = nebius.discover_embedding_dimension()
    store = get_pinecone_store()
    store.ensure_index(dim)
    if reset_namespace:
        print(f"Clearing namespace '{settings.pinecone_namespace}' for idempotent reindex…")
        store.delete_namespace()

    texts = [c.chunk_text for c in all_chunks]
    print(f"Embedding {len(texts)} chunks with {settings.nebius_embed_model}…")
    vectors = []
    batch = 16
    for i in range(0, len(texts), batch):
        vectors.extend(nebius.embed(texts[i : i + batch]))
        print(f"  embedded {min(i + batch, len(texts))}/{len(texts)}")

    ids = [c.chunk_id for c in all_chunks]
    metas = [c.to_metadata() for c in all_chunks]
    upserted = store.upsert_chunks(ids, vectors, metas)
    print(f"Upserted {upserted} vectors into Pinecone index '{settings.pinecone_index}'")
    print("Ingestion complete.")


if __name__ == "__main__":
    main()
