"""Build local BM25 index without calling Nebius/Pinecone (offline prep)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.data.loader import list_policy_files, load_policies  # noqa: E402
from app.rag.bm25_store import BM25Store  # noqa: E402
from app.rag.chunking import chunk_document  # noqa: E402


def main() -> None:
    policies = load_policies()
    chunks = []
    for path in list_policy_files():
        policy = policies.get(path.stem)
        if not policy:
            continue
        chunks.extend(
            chunk_document(
                path,
                policy_id=policy.policy_id,
                jurisdiction=policy.jurisdiction,
                policy_form_version=policy.policy_form_version,
                effective_date=policy.effective_date,
                expiration_date=policy.expiration_date,
            )
        )
    store = BM25Store()
    store.build(chunks)
    print(f"BM25 index built with {len(chunks)} chunks at data/indexes/")


if __name__ == "__main__":
    main()
