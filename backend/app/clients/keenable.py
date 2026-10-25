"""Keenable web search API client for external research."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

KEENABLE_SEARCH_URL = "https://api.keenable.ai/v1/search"


class KeenableError(RuntimeError):
    pass


class KeenableClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        key = self.settings.keenable_api_key or ""
        return bool(key) and not key.startswith("your_")

    def health_check(self) -> Dict[str, Any]:
        if not self.configured:
            return {
                "ok": False,
                "error": "KEENABLE_API_KEY not configured",
                "configured": False,
            }
        return {
            "ok": True,
            "configured": True,
            "note": "API key present (live search not pinged)",
        }

    def search(
        self,
        query: str,
        *,
        max_results: Optional[int] = None,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.configured:
            raise KeenableError("KEENABLE_API_KEY is missing or still a placeholder")
        max_results = max_results or self.settings.keenable_max_results
        mode = mode or self.settings.keenable_search_mode
        payload = {
            "query": query,
            "mode": mode,
            "max_results": max_results,
        }
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.settings.keenable_api_key,
        }
        try:
            with httpx.Client(timeout=self.settings.http_timeout_seconds) as client:
                resp = client.post(KEENABLE_SEARCH_URL, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise KeenableError(f"Keenable request failed: {exc}") from exc

        results: List[Dict[str, Any]] = []
        for item in data.get("results") or []:
            snippet = item.get("snippet") or item.get("description") or ""
            results.append(
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "content": str(snippet)[:500],
                    "description": item.get("description"),
                    "published_at": item.get("published_at"),
                }
            )
        return {
            "query": query,
            "mode": data.get("mode") or mode,
            "answer": None,
            "results": results,
            "provider": "keenable",
            "disclaimer": (
                "Web results are investigative aids only. Prices and facts may be incomplete "
                "or outdated. Not a settlement offer or coverage decision."
            ),
        }


@lru_cache
def get_keenable() -> KeenableClient:
    return KeenableClient()
