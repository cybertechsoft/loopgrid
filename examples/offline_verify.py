"""Verify a portable evidence ZIP without a running LoopGrid server."""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from verifier.loopgrid_verify import verify_bundle

if len(sys.argv)<2: raise SystemExit("Usage: python examples/offline_verify.py <evidence.zip>")
result=verify_bundle(sys.argv[1])
print("valid:",result["valid"])
print("events:",result.get("events"))
print("key:",result.get("key_identity",{}).get("computed_key_id"))
