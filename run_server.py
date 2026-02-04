#!/usr/bin/env python3
"""
LoopGrid Server
===============

Start the LoopGrid control plane server.

Usage:
    python run_server.py
    
Or:
    uvicorn backend.app.main:app --reload --port 8000
"""

import uvicorn

if __name__ == "__main__":
    print()
    print("=" * 50)
    print("  LoopGrid - Control Plane for AI Decisions")
    print("=" * 50)
    print()
    print("  API Docs:  http://localhost:8000/docs")
    print("  Health:    http://localhost:8000/health")
    print()
    print("  Press Ctrl+C to stop")
    print()
    
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
