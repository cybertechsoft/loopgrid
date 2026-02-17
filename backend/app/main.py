"""
LoopGrid Control Plane
======================

The control plane for AI decision reliability.

Provides:
- Decision ledger (immutable, hash-chained records)
- Replay engine (live LLM or simulated re-execution)
- Human correction loop (ground truth)
- Compliance reports (EU AI Act mapping)
- Ledger integrity verification

Run with:
    python run_server.py
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .database import create_tables
from .routers import decisions, replays, integrity, compliance


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    create_tables()
    yield


app = FastAPI(
    title="LoopGrid",
    description="Control Plane for AI Decision Reliability",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core routers
app.include_router(decisions.router, prefix="/v1", tags=["decisions"])
app.include_router(replays.router, prefix="/v1", tags=["replays"])
app.include_router(integrity.router, prefix="/v1", tags=["integrity"])
app.include_router(compliance.router, prefix="/v1", tags=["compliance"])


@app.get("/")
async def root():
    return {
        "name": "LoopGrid",
        "version": "0.1.0",
        "description": "Control Plane for AI Decision Reliability",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0", "service": "loopgrid"}
