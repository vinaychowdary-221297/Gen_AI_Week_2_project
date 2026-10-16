"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

# Corporate SSL inspection (Windows): use OS trust store for Nebius/Pinecone
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.data.loader import load_claims
from app.rag.bm25_store import get_bm25_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("claims-intel")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting Insurance Claims Intelligence backend")
    logger.info("Chat model: %s | Embed model: %s", settings.nebius_chat_model, settings.nebius_embed_model)

    # Load local datasets early so misconfiguration fails fast
    try:
        claims = load_claims()
        logger.info("Loaded %s synthetic claims", len(claims))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Claims data not loaded yet: %s (run scripts/generate_data.py)", exc)

    bm25 = get_bm25_store()
    if bm25.chunks:
        logger.info("BM25 index ready with %s chunks", len(bm25.chunks))
    else:
        logger.warning("BM25 index empty — run scripts/ingest_docs.py after configuring .env")

    # Soft credential notice (do not crash demo UI health)
    try:
        settings.require_credentials()
        logger.info("Nebius and Pinecone credentials detected")
    except ValueError as exc:
        logger.warning("%s", exc)

    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Insurance Claims Intelligence",
        description="Agentic Hybrid RAG claim investigation platform",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")

    @app.get("/")
    async def root():
        return {
            "name": "Insurance Claims Intelligence",
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
