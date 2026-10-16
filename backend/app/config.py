"""Application configuration loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_ROOT / "data"
POLICIES_DIR = DATA_DIR / "policies"
CLAIMS_DIR = DATA_DIR / "claims"
INDEXES_DIR = DATA_DIR / "indexes"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Nebius
    nebius_api_key: str = Field(default="", alias="NEBIUS_API_KEY")
    nebius_base_url: str = Field(
        default="https://api.tokenfactory.nebius.com/v1/",
        alias="NEBIUS_BASE_URL",
    )
    nebius_chat_model: str = Field(default="openai/gpt-oss-120b", alias="NEBIUS_CHAT_MODEL")
    nebius_embed_model: str = Field(
        default="Qwen/Qwen3-Embedding-8B", alias="NEBIUS_EMBED_MODEL"
    )

    # Pinecone
    pinecone_api_key: str = Field(default="", alias="PINECONE_API_KEY")
    pinecone_index: str = Field(default="claims-intelligence", alias="PINECONE_INDEX")
    pinecone_cloud: str = Field(default="aws", alias="PINECONE_CLOUD")
    pinecone_region: str = Field(default="us-east-1", alias="PINECONE_REGION")
    pinecone_namespace: str = Field(default="policy-docs", alias="PINECONE_NAMESPACE")

    # Hybrid RAG
    rrf_k: int = Field(default=60, alias="RRF_K")
    top_k_bm25: int = Field(default=8, alias="TOP_K_BM25")
    top_k_dense: int = Field(default=8, alias="TOP_K_DENSE")
    top_k_rrf: int = Field(default=6, alias="TOP_K_RRF")
    chunk_size: int = Field(default=800, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=120, alias="CHUNK_OVERLAP")
    enable_rerank: bool = Field(default=False, alias="ENABLE_RERANK")

    # Agent
    max_tool_calls: int = Field(default=12, alias="MAX_TOOL_CALLS")
    agent_timeout_seconds: int = Field(default=120, alias="AGENT_TIMEOUT_SECONDS")

    # Server
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    # Timeouts / retries
    http_timeout_seconds: float = 60.0
    max_retries: int = 3

    @field_validator("nebius_base_url")
    @classmethod
    def normalize_base_url(cls, v: str) -> str:
        return v.rstrip("/") + "/"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def require_credentials(self) -> None:
        missing = []
        if not self.nebius_api_key or self.nebius_api_key.startswith("your_"):
            missing.append("NEBIUS_API_KEY")
        if not self.pinecone_api_key or self.pinecone_api_key.startswith("your_"):
            missing.append("PINECONE_API_KEY")
        if missing:
            raise ValueError(
                f"Missing or placeholder credentials: {', '.join(missing)}. "
                "Copy backend/.env.example to backend/.env and set real values."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
