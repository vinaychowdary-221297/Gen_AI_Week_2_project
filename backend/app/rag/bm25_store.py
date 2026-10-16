"""Local BM25 keyword retrieval over versioned document chunks."""

from __future__ import annotations

import json
import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi

from app.config import INDEXES_DIR
from app.rag.chunking import DocumentChunk


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_$#./-]+", text.lower())


class BM25Store:
    def __init__(self) -> None:
        self.chunks: List[Dict[str, Any]] = []
        self._corpus_tokens: List[List[str]] = []
        self._bm25: Optional[BM25Okapi] = None
        INDEXES_DIR.mkdir(parents=True, exist_ok=True)
        self._json_path = INDEXES_DIR / "bm25_chunks.json"
        self._pkl_path = INDEXES_DIR / "bm25_index.pkl"

    def build(self, chunks: List[DocumentChunk]) -> None:
        self.chunks = [c.to_metadata() for c in chunks]
        self._corpus_tokens = [_tokenize(c["chunk_text"]) for c in self.chunks]
        self._bm25 = BM25Okapi(self._corpus_tokens) if self._corpus_tokens else None
        self.save()

    def save(self) -> None:
        self._json_path.write_text(json.dumps(self.chunks, indent=2), encoding="utf-8")
        with self._pkl_path.open("wb") as f:
            pickle.dump({"tokens": self._corpus_tokens}, f)

    def load(self) -> bool:
        if not self._json_path.exists():
            return False
        self.chunks = json.loads(self._json_path.read_text(encoding="utf-8"))
        if self._pkl_path.exists():
            with self._pkl_path.open("rb") as f:
                data = pickle.load(f)
            self._corpus_tokens = data.get("tokens") or [
                _tokenize(c["chunk_text"]) for c in self.chunks
            ]
        else:
            self._corpus_tokens = [_tokenize(c["chunk_text"]) for c in self.chunks]
        self._bm25 = BM25Okapi(self._corpus_tokens) if self._corpus_tokens else None
        return True

    def search(
        self,
        query: str,
        top_k: int = 8,
        policy_id: Optional[str] = None,
        document_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self._bm25 or not self.chunks:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results: List[Dict[str, Any]] = []
        for i in ranked_idx:
            meta = self.chunks[i]
            if policy_id and meta.get("policy_id") != policy_id:
                continue
            if document_type and meta.get("document_type") != document_type:
                continue
            if scores[i] <= 0:
                continue
            row = dict(meta)
            row["bm25_score"] = float(scores[i])
            row["score"] = float(scores[i])
            results.append(row)
            if len(results) >= top_k:
                break
        return results


_bm25: Optional[BM25Store] = None


def get_bm25_store() -> BM25Store:
    global _bm25
    if _bm25 is None:
        _bm25 = BM25Store()
        _bm25.load()
    return _bm25
