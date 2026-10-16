"""Document text extraction and chunking."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from app.config import get_settings


@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    document_type: str
    policy_id: str
    jurisdiction: str
    section: str
    page_number: Optional[int]
    source_filename: str
    chunk_text: str
    policy_form_version: str
    effective_date: str
    expiration_date: str

    def to_metadata(self) -> dict:
        return asdict(self)


def extract_text(path: Path) -> List[tuple[Optional[int], str]]:
    """Return list of (page_number|None, text)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    text = path.read_text(encoding="utf-8")
    return [(None, text)]


def _extract_pdf(path: Path) -> List[tuple[Optional[int], str]]:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for PDF ingestion") from exc
    pages: List[tuple[Optional[int], str]] = []
    with fitz.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            pages.append((i, page.get_text("text")))
    return pages


def _split_sections(text: str) -> List[tuple[str, str]]:
    """Split markdown/txt on ## headings when present."""
    parts = re.split(r"(?m)^(#{1,3}\s+.+)$", text)
    if len(parts) == 1:
        return [("General", text.strip())]
    sections: List[tuple[str, str]] = []
    preamble = parts[0].strip()
    if preamble:
        sections.append(("Preamble", preamble))
    for i in range(1, len(parts), 2):
        heading = parts[i].lstrip("#").strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        sections.append((heading, body))
    return sections


def chunk_text(
    text: str,
    chunk_size: Optional[int] = None,
    overlap: Optional[int] = None,
) -> List[str]:
    settings = get_settings()
    size = chunk_size or settings.chunk_size
    ov = overlap or settings.chunk_overlap
    words = text.split()
    if not words:
        return []
    chunks: List[str] = []
    step = max(1, size - ov)
    for start in range(0, len(words), step):
        piece = " ".join(words[start : start + size])
        if piece.strip():
            chunks.append(piece.strip())
        if start + size >= len(words):
            break
    return chunks


def stable_chunk_id(document_id: str, index: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{document_id}::c{index:04d}::{digest}"


def chunk_document(
    path: Path,
    *,
    policy_id: str,
    jurisdiction: str,
    policy_form_version: str,
    effective_date: str,
    expiration_date: str,
    document_type: str = "policy",
) -> List[DocumentChunk]:
    pages = extract_text(path)
    document_id = path.stem
    results: List[DocumentChunk] = []
    global_idx = 0
    for page_number, page_text in pages:
        for section, body in _split_sections(page_text):
            for piece in chunk_text(body):
                cid = stable_chunk_id(document_id, global_idx, piece)
                results.append(
                    DocumentChunk(
                        chunk_id=cid,
                        document_id=document_id,
                        document_type=document_type,
                        policy_id=policy_id,
                        jurisdiction=jurisdiction,
                        section=section,
                        page_number=page_number,
                        source_filename=path.name,
                        chunk_text=piece,
                        policy_form_version=policy_form_version,
                        effective_date=effective_date,
                        expiration_date=expiration_date,
                    )
                )
                global_idx += 1
    return results
