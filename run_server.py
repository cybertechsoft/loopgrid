#!/usr/bin/env python3
"""
LoopGrid Server — Start the control plane.
Usage: python run_server.py
"""

import uvicorn

if __name__ == "__main__":
    print()
    print("=" * 50)
    print("  LoopGrid - Control Plane for AI Decisions")
    print("=" * 50)
    print()
    print("  API Docs:    http://localhost:8000/docs")
    print("  Health:      http://localhost:8000/health")
    print("  Compliance:  http://localhost:8000/v1/compliance/report")
    print("  Integrity:   http://localhost:8000/v1/integrity/verify")
    print()
    print("  Press Ctrl+C to stop")
    print()
    
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
