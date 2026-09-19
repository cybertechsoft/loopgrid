from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + path.resolve().as_posix()


def _prepare_local_environment(state_dir: Path) -> None:
    """Configure an isolated, local-only LoopGrid evaluation environment.

    Environment variables are set before importing the LoopGrid application because
    runtime settings and the signing provider are initialized at import time.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    os.environ["LOOPGRID_ENV"] = "development"
    os.environ["LOOPGRID_REQUIRE_USER_AUTH"] = "false"
    os.environ["LOOPGRID_DATABASE_URL"] = _sqlite_url(state_dir / "loopgrid.db")
    os.environ["LOOPGRID_SIGNER_PROVIDER"] = "local_ed25519"
    os.environ["LOOPGRID_SIGNING_KEY_PATH"] = str(state_dir / "signing-key.pem")
    os.environ["LOOPGRID_PUBLIC_KEY_PATH"] = str(state_dir / "signing-public.pem")
    os.environ["LOOPGRID_PAYLOAD_KEY_PATH"] = str(state_dir / "payload-key.bin")
    os.environ["LOOPGRID_STRICT_PRODUCTION_SAFETY"] = "true"


def run(output_dir: Path) -> int:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Never reuse an existing evaluation database or signing key. The quickstart is
    # intended to be deterministic from the user's point of view and isolated from
    # any real/local LoopGrid deployment they may already have.
    with tempfile.TemporaryDirectory(prefix="loopgrid-quickstart-") as tmp:
        state_dir = Path(tmp)
        _prepare_local_environment(state_dir)

        try:
            from fastapi.testclient import TestClient
            from app.main import app
            from verifier.loopgrid_verify import verify_bundle
        except Exception as exc:  # pragma: no cover - friendly CLI path
            print("[FAIL] LoopGrid dependencies are not installed.")
            print("Run: python -m pip install -r requirements.txt")
            print(f"Detail: {type(exc).__name__}: {exc}")
            return 1

        bundle_path = output_dir / "evidence.zip"
        trusted_key_path = output_dir / "trusted-public-key.pem"
        summary_path = output_dir / "quickstart-result.json"

        for path in (bundle_path, trusted_key_path, summary_path):
            if path.exists():
                path.unlink()

        print("LoopGrid quickstart")
        print("-------------------")
        print("Creating an isolated local evaluation using SQLite and a temporary Ed25519 signer...")

        try:
            with TestClient(app) as client:
                demo = client.post("/api/v1/demo/refund")
                demo.raise_for_status()
                payload = demo.json()
                decision_id = payload["summary"]["decision_id"]

                evidence = client.get(
                    f"/api/v1/decisions/{decision_id}/evidence",
                    params={"include_payloads": "false"},
                )
                evidence.raise_for_status()
                bundle_path.write_bytes(evidence.content)

                public_key = client.get("/api/v1/public-key.pem")
                public_key.raise_for_status()
                trusted_key_path.write_bytes(public_key.content)

            result = verify_bundle(
                str(bundle_path),
                trusted_public_key=str(trusted_key_path),
            )
        except Exception as exc:
            print(f"[FAIL] Quickstart failed: {type(exc).__name__}: {exc}")
            return 1

        summary = {
            "decision_id": decision_id,
            "workspace_id": payload["summary"].get("workspace_id"),
            "decision_type": payload["summary"].get("decision_type"),
            "lifecycle": payload["summary"].get("lifecycle"),
            "coverage": payload.get("coverage"),
            "verification": result,
            "artifacts": {
                "evidence": str(bundle_path),
                "trusted_public_key": str(trusted_key_path),
            },
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        print(f"[OK] Decision captured: {decision_id}")
        print(f"[OK] Evidence exported: {bundle_path}")
        print(f"[OK] Trusted public key exported: {trusted_key_path}")
        print(f"[OK] Evidence coverage: {payload['coverage']['score']}%")
        if result.get("valid"):
            print("[OK] VERIFIED")
            print("     The exported bundle verified with an out-of-band trusted public key.")
            print(f"     Details: {summary_path}")
            return 0

        print("[FAIL] INVALID")
        print(json.dumps(result, indent=2))
        return 2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create and independently verify a synthetic LoopGrid evidence bundle locally."
    )
    parser.add_argument(
        "--output-dir",
        default="demo-output",
        help="Directory for evidence.zip, trusted-public-key.pem, and result JSON (default: demo-output)",
    )
    args = parser.parse_args()
    raise SystemExit(run(Path(args.output_dir)))


if __name__ == "__main__":
    main()
