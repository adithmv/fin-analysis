"""Loopback-only, read-only bridge for CPU semantic search; no cloud model calls."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from shared.db import get_client
from shared.logbook import sanitize
from .main import settings
from .search import search, similar

app = FastAPI(title="Local news memory", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
app.add_middleware(
    CORSMiddleware, allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"], allow_methods=["GET"]
)


@app.get("/health")
def health():
    return {"status": "ready", "mode": "local CPU, read-only"}


@app.get("/search")
def query(
    q: str = Query(min_length=1, max_length=500),
    symbol: str | None = None,
    start: str | None = None,
    end: str | None = None,
    event: str | None = None,
    k: int = Query(default=10, ge=1, le=20),
):
    try:
        return search(get_client(), settings()[0], q, symbol, k, start, end, event)
    except Exception as exc:
        raise HTTPException(503, str(sanitize(exc))) from None


@app.get("/similar/{article_id}")
def neighbors(article_id: str, symbol: str | None = None):
    from uuid import UUID

    try:
        UUID(article_id)
        return similar(get_client(), settings()[0], article_id, symbol)
    except Exception as exc:
        raise HTTPException(503, str(sanitize(exc))) from None
