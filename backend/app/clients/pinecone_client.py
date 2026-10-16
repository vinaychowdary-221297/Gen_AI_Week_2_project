"""Pinecone vector database integration."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Sequence

from pinecone import Pinecone, ServerlessSpec

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class PineconeConfigurationError(RuntimeError):
    """Raised for missing credentials or incompatible indexes."""


class PineconeStore:
    """Manage a dense cosine index for policy document chunks."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.pinecone_api_key or self.settings.pinecone_api_key.startswith(
            "your_"
        ):
            raise PineconeConfigurationError(
                "PINECONE_API_KEY is missing. Set it in backend/.env."
            )
        self._pc = Pinecone(api_key=self.settings.pinecone_api_key)
        self._index = None
        self._dimension: Optional[int] = None

    @property
    def index_name(self) -> str:
        return self.settings.pinecone_index

    @property
    def namespace(self) -> str:
        return self.settings.pinecone_namespace

    def health_check(self) -> Dict[str, Any]:
        try:
            names = [idx.name for idx in self._pc.list_indexes()]
            exists = self.index_name in names
            ready = False
            dim = None
            if exists:
                desc = self._pc.describe_index(self.index_name)
                ready = bool(getattr(desc, "status", {}).get("ready", True))
                dim = getattr(desc, "dimension", None)
            return {
                "ok": True,
                "index": self.index_name,
                "exists": exists,
                "ready": ready if exists else False,
                "dimension": dim,
                "namespace": self.namespace,
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "index": self.index_name}

    def ensure_index(self, dimension: int) -> None:
        """Create the configured index if missing; validate if present."""
        self._dimension = dimension
        existing = {idx.name: idx for idx in self._pc.list_indexes()}
        if self.index_name not in existing:
            logger.info(
                "Creating Pinecone index '%s' dim=%s metric=cosine",
                self.index_name,
                dimension,
            )
            self._pc.create_index(
                name=self.index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=self.settings.pinecone_cloud,
                    region=self.settings.pinecone_region,
                ),
            )
            self._wait_ready()
        else:
            desc = self._pc.describe_index(self.index_name)
            existing_dim = getattr(desc, "dimension", None)
            if existing_dim is not None and int(existing_dim) != int(dimension):
                raise PineconeConfigurationError(
                    f"Index '{self.index_name}' has dimension {existing_dim}, "
                    f"but Nebius embeddings are dimension {dimension}. "
                    "Create a new index or change PINECONE_INDEX / embedding model."
                )
            status = getattr(desc, "status", {}) or {}
            if not status.get("ready", True):
                self._wait_ready()
        self._index = self._pc.Index(self.index_name)

    def _wait_ready(self, timeout: float = 120.0) -> None:
        started = time.time()
        while time.time() - started < timeout:
            desc = self._pc.describe_index(self.index_name)
            status = getattr(desc, "status", {}) or {}
            if status.get("ready", False):
                logger.info("Pinecone index '%s' is ready", self.index_name)
                return
            time.sleep(2)
        raise PineconeConfigurationError(
            f"Timed out waiting for Pinecone index '{self.index_name}' to become ready."
        )

    def _get_index(self):
        if self._index is None:
            self._index = self._pc.Index(self.index_name)
        return self._index

    def upsert_chunks(
        self,
        ids: Sequence[str],
        vectors: Sequence[Sequence[float]],
        metadatas: Sequence[Dict[str, Any]],
        batch_size: int = 64,
    ) -> int:
        """Idempotent batch upsert of document chunks."""
        index = self._get_index()
        total = 0
        batch: List[Dict[str, Any]] = []
        for vid, values, meta in zip(ids, vectors, metadatas):
            # Pinecone metadata values must be str/number/bool/list[str]
            clean_meta = _sanitize_metadata(meta)
            batch.append({"id": vid, "values": list(values), "metadata": clean_meta})
            if len(batch) >= batch_size:
                index.upsert(vectors=batch, namespace=self.namespace)
                total += len(batch)
                batch = []
        if batch:
            index.upsert(vectors=batch, namespace=self.namespace)
            total += len(batch)
        return total

    def query(
        self,
        vector: Sequence[float],
        top_k: int = 8,
        filter: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
    ) -> List[Dict[str, Any]]:
        index = self._get_index()
        response = index.query(
            vector=list(vector),
            top_k=top_k,
            namespace=self.namespace,
            filter=filter,
            include_metadata=include_metadata,
        )
        matches = []
        for m in getattr(response, "matches", []) or []:
            matches.append(
                {
                    "id": m.id,
                    "score": float(m.score or 0.0),
                    "metadata": dict(m.metadata or {}),
                }
            )
        return matches

    def delete_namespace(self) -> None:
        """Clear demo namespace for clean reindexing."""
        index = self._get_index()
        try:
            index.delete(delete_all=True, namespace=self.namespace)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Namespace delete skipped: %s", exc)


def _sanitize_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in meta.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            out[key] = value
        elif isinstance(value, list):
            out[key] = [str(v) for v in value]
        else:
            out[key] = str(value)
    # Pinecone limits metadata size; truncate long chunk text for storage
    if "chunk_text" in out and isinstance(out["chunk_text"], str):
        out["chunk_text"] = out["chunk_text"][:35000]
    return out


_store: Optional[PineconeStore] = None


def get_pinecone_store() -> PineconeStore:
    global _store
    if _store is None:
        _store = PineconeStore()
    return _store
