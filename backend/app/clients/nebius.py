"""Nebius Token Factory client (OpenAI-compatible API)."""

from __future__ import annotations

import hashlib
import logging
import ssl
import time
from typing import Any, Dict, List, Optional, Sequence

import httpx
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _build_http_client(timeout: float) -> httpx.Client:
    """Use the OS trust store so corporate SSL inspection works on Windows."""
    try:
        import truststore

        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        return httpx.Client(verify=ctx, timeout=timeout)
    except Exception:  # noqa: BLE001
        logger.warning("truststore unavailable; falling back to default SSL verify")
        return httpx.Client(timeout=timeout)


class NebiusConfigurationError(RuntimeError):
    """Raised when Nebius is misconfigured (e.g. no tool calling)."""


class NebiusClient:
    """Wrapper around the OpenAI SDK pointed at Nebius Token Factory."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._http = _build_http_client(self.settings.http_timeout_seconds)
        self._client = OpenAI(
            api_key=self.settings.nebius_api_key,
            base_url=self.settings.nebius_base_url,
            timeout=self.settings.http_timeout_seconds,
            max_retries=0,  # we handle retries explicitly
            http_client=self._http,
        )
        self._embed_dim: Optional[int] = None
        self._embed_cache: Dict[str, List[float]] = {}
        self._tool_calling_ok: Optional[bool] = None

    @property
    def chat_model(self) -> str:
        return self.settings.nebius_chat_model

    @property
    def embed_model(self) -> str:
        return self.settings.nebius_embed_model

    def health_check(self) -> Dict[str, Any]:
        """Lightweight connectivity probe."""
        try:
            # Prefer models.list when available; fall back to a tiny embed call.
            models = self._client.models.list()
            ids = [m.id for m in getattr(models, "data", [])][:20]
            return {
                "ok": True,
                "base_url": self.settings.nebius_base_url,
                "chat_model": self.chat_model,
                "embed_model": self.embed_model,
                "sample_models": ids,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": str(exc),
                "base_url": self.settings.nebius_base_url,
            }

    def validate_tool_calling(self) -> None:
        """Confirm the chat model accepts tools; raise clear error if not."""
        if self._tool_calling_ok is True:
            return
        try:
            response = self._client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with the single word OK. Do not call tools.",
                    }
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "ping",
                            "description": "Health ping tool",
                            "parameters": {
                                "type": "object",
                                "properties": {},
                                "additionalProperties": False,
                            },
                        },
                    }
                ],
                tool_choice="none",
                max_tokens=16,
                temperature=0,
            )
            _ = response.choices[0].message
            self._tool_calling_ok = True
            logger.info("Nebius chat model %s accepts tool schemas", self.chat_model)
        except APIStatusError as exc:
            body = getattr(exc, "body", None) or str(exc)
            raise NebiusConfigurationError(
                f"Configured chat model '{self.chat_model}' rejected tool/function "
                f"calling schemas. Choose a Nebius model that supports tools. "
                f"API error: {body}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise NebiusConfigurationError(
                f"Unable to validate tool calling for '{self.chat_model}': {exc}"
            ) from exc

    def discover_embedding_dimension(self) -> int:
        """Probe embedding size once and cache it."""
        if self._embed_dim is not None:
            return self._embed_dim
        vectors = self.embed(["dimension probe"])
        if not vectors or not vectors[0]:
            raise NebiusConfigurationError(
                f"Embedding model '{self.embed_model}' returned an empty vector."
            )
        self._embed_dim = len(vectors[0])
        logger.info(
            "Discovered embedding dimension %s for %s",
            self._embed_dim,
            self.embed_model,
        )
        return self._embed_dim

    @staticmethod
    def _cache_key(text: str, model: str) -> str:
        return hashlib.sha256(f"{model}::{text}".encode("utf-8")).hexdigest()

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed texts with caching for unchanged content."""
        if not texts:
            return []
        results: List[Optional[List[float]]] = [None] * len(texts)
        to_embed: List[str] = []
        to_embed_idx: List[int] = []

        for i, text in enumerate(texts):
            key = self._cache_key(text, self.embed_model)
            if key in self._embed_cache:
                results[i] = self._embed_cache[key]
            else:
                to_embed.append(text)
                to_embed_idx.append(i)

        if to_embed:
            response = self._client.embeddings.create(
                model=self.embed_model,
                input=list(to_embed),
                encoding_format="float",
            )
            data = sorted(response.data, key=lambda d: d.index)
            for local_i, item in enumerate(data):
                vec = list(item.embedding)
                global_i = to_embed_idx[local_i]
                results[global_i] = vec
                key = self._cache_key(to_embed[local_i], self.embed_model)
                self._embed_cache[key] = vec
                if self._embed_dim is None:
                    self._embed_dim = len(vec)

        return [r or [] for r in results]

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Any = "auto",
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> Any:
        """Chat completion with optional tools."""
        kwargs: Dict[str, Any] = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        started = time.perf_counter()
        try:
            response = self._client.chat.completions.create(**kwargs)
        except RateLimitError:
            logger.warning("Nebius rate limit hit; retrying…")
            raise
        except APIStatusError as exc:
            logger.error("Nebius API error: %s", exc)
            raise
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            logger.debug("Nebius chat completed in %.0fms", elapsed)
        return response


_nebius: Optional[NebiusClient] = None


def get_nebius() -> NebiusClient:
    global _nebius
    if _nebius is None:
        _nebius = NebiusClient()
    return _nebius
