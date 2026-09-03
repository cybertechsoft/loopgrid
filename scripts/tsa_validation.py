from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate LoopGrid RFC3161 TSA integration")
    ap.add_argument("--url", default=os.getenv("LOOPGRID_TSA_URL"))
    args = ap.parse_args()
    if not args.url:
        raise SystemExit("Set LOOPGRID_TSA_URL or pass --url")
    os.environ["LOOPGRID_TSA_URL"] = args.url

    # Import after setting the URL because LoopGrid settings are loaded at import time.
    from app.timestamping import request_rfc3161_timestamp

    digest = hashlib.sha256(b"LoopGrid RFC3161 external timestamp validation").hexdigest()
    result = request_rfc3161_timestamp(digest)
    public = {k: v for k, v in result.items() if k != "response_b64"}
    print(json.dumps(public, indent=2, default=str))
    token_bytes = len(base64.b64decode(result["response_b64"])) if result.get("response_b64") else 0
    print(f"Timestamp token bytes: {token_bytes}")
    ok = result.get("external_timestamp") is True and result.get("imprint_valid") is True and result.get("nonce_valid") is True
    print("TSA VALIDATION RESULT: PASS" if ok else "TSA VALIDATION RESULT: FAIL")
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()
