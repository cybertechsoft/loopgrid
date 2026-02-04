"""
LoopGrid Control Plane
======================

The control plane for AI decision reliability.

This is the main FastAPI application that provides:
- Decision ledger (immutable records)
- Replay engine (forked executions)
- Human correction loop (ground truth)

Run with:
    python run_server.py
    
Or:
    uvicorn backend.app.main:app --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .database import create_tables, engine
from .routers import decisions, replays


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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(decisions.router, prefix="/v1", tags=["decisions"])
app.include_router(replays.router, prefix="/v1", tags=["replays"])


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "LoopGrid",
        "version": "0.1.0",
        "description": "Control Plane for AI Decision Reliability",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "loopgrid"
    }
