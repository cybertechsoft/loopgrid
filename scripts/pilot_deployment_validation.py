#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path
import httpx


def read_env(path: Path) -> dict[str,str]:
    out={}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line=raw.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k,v=line.split("=",1); out[k.strip()]=v.strip()
    return out


def wait_ready(base: str, seconds: int=60):
    end=time.time()+seconds
    last=None
    while time.time()<end:
        try:
            r=httpx.get(base+"/ready",timeout=3); last=f"{r.status_code} {r.text[:200]}"
            if r.status_code==200 and r.json().get("ready") is True:return r.json()
        except Exception as e:last=repr(e)
        time.sleep(2)
    raise RuntimeError(f"LoopGrid did not become ready within {seconds}s: {last}")


def prepare_verifier_python() -> str:
    """Return a Python interpreter that can run the standalone verifier.

    The Docker deployment includes cryptography inside the application image, but the
    verifier intentionally runs outside the service process. On a fresh Windows host,
    the Python used to launch the deployment validator may not have verifier-only crypto
    dependencies installed. Keep the experience one-command by creating a small isolated
    tool environment when needed instead of modifying the user's global Python.
    """
    probe=[sys.executable,"-c","import cryptography, asn1crypto"]
    if subprocess.run(probe,capture_output=True,text=True).returncode==0:
        return sys.executable

    env_dir=Path(tempfile.gettempdir())/"loopgrid-v080-verifier-venv"
    py=env_dir/("Scripts/python.exe" if os.name=="nt" else "bin/python")
    if py.exists():
        check=subprocess.run([str(py),"-c","import cryptography, asn1crypto"],capture_output=True,text=True)
        if check.returncode==0:
            print("[PASS] Isolated offline-verifier environment ready")
            return str(py)

    print("[INFO] Preparing isolated offline-verifier environment (one-time setup)...")
    if not env_dir.exists():
        r=subprocess.run([sys.executable,"-m","venv",str(env_dir)],text=True)
        if r.returncode!=0:
            raise RuntimeError("could not create isolated offline-verifier Python environment")

    install=subprocess.run(
        [str(py),"-m","pip","install","--disable-pip-version-check","cryptography>=42,<47","asn1crypto>=1.5,<2"],
        text=True,
    )
    if install.returncode!=0:
        raise RuntimeError("could not install standalone verifier dependencies")
    check=subprocess.run([str(py),"-c","import cryptography, asn1crypto"],capture_output=True,text=True)
    if check.returncode!=0:
        raise RuntimeError("standalone verifier dependency check failed after installation")
    print("[PASS] Isolated offline-verifier environment ready")
    return str(py)


def main():
    ap=argparse.ArgumentParser(description="One-command HTTP validation for a v0.8 Docker design-partner deployment")
    ap.add_argument("--base-url",default="http://127.0.0.1:8000")
    ap.add_argument("--env-file",default=".env")
    ap.add_argument("--output-dir",default="pilot-validation-output-v080")
    args=ap.parse_args()
    base=args.base_url.rstrip("/")
    env=read_env(Path(args.env_file))
    platform=env.get("LOOPGRID_PLATFORM_ADMIN_KEY")
    if not platform:raise SystemExit("LOOPGRID_PLATFORM_ADMIN_KEY is missing from the env file")

    ready=wait_ready(base)
    print(f"[PASS] Readiness - {json.dumps(ready)}")
    info=httpx.get(base+"/api/v1/system/info",timeout=10).json()
    if info.get("database",{}).get("provider")!="postgresql":raise RuntimeError("deployment is not using PostgreSQL")
    if info.get("deployment_security",{}).get("unsafe_configuration"):raise RuntimeError("production safety guard reports unsafe configuration")
    print("[PASS] PostgreSQL deployment posture")
    print("[PASS] Production safety posture")

    anon=httpx.get(base+"/api/v1/decisions?workspace_id=default",timeout=10)
    if anon.status_code!=401:raise RuntimeError(f"anonymous decision read expected 401, got {anon.status_code}")
    print("[PASS] Anonymous evidence read blocked")

    issued=httpx.post(
        base+"/api/v1/workspaces/default/keys",
        headers={"X-LoopGrid-Key":platform},
        json={"name":"v0.8 deployment validator admin","description":"temporary release validation key","scopes":["admin","ingest","read","review"],"expires_in_days":1},
        timeout=15,
    )
    issued.raise_for_status(); j=issued.json(); key=j["api_key"]; key_id=j["key_id"]
    print(f"[PASS] Temporary admin service identity issued - {key_id}")
    scenario_key_id=None
    try:
        verifier_python=prepare_verifier_python()
        cmd=[sys.executable,"scripts/real_scenario_test.py","--admin-key",key,"--output-dir",args.output_dir]
        child_env=os.environ.copy()
        child_env.setdefault("PYTHONIOENCODING","utf-8")
        child_env.setdefault("PYTHONUTF8","1")
        child_env["LOOPGRID_VERIFIER_PYTHON"]=verifier_python
        proc=subprocess.run(cmd,text=True,encoding="utf-8",errors="replace",capture_output=True,timeout=180,env=child_env)
        if proc.stdout:
            print(proc.stdout.rstrip())
            m=re.search(r"Scoped service API key issued\s+-\s+(key_[0-9a-fA-F]+)",proc.stdout)
            if m: scenario_key_id=m.group(1)
        if proc.returncode!=0:
            if proc.stderr:print(proc.stderr.rstrip(),file=sys.stderr)
            raise RuntimeError(f"real scenario exited {proc.returncode}")
        if "REAL SCENARIO RESULT: PASS" not in proc.stdout:raise RuntimeError("real scenario did not report PASS")
        print("[PASS] Full PostgreSQL evidence scenario")
    finally:
        if scenario_key_id:
            try:
                sr=httpx.delete(base+f"/api/v1/workspaces/default/keys/{scenario_key_id}",headers={"X-LoopGrid-Key":key},timeout=10)
                if sr.status_code<400:print(f"[PASS] Scenario service identity revoked - {scenario_key_id}")
                else:print(f"[WARN] Scenario service key cleanup returned {sr.status_code}")
            except Exception as e:print(f"[WARN] Scenario service key cleanup failed: {type(e).__name__}")
        try:
            r=httpx.delete(base+f"/api/v1/workspaces/default/keys/{key_id}",headers={"X-LoopGrid-Key":key},timeout=10)
            if r.status_code<400:print(f"[PASS] Temporary admin service identity revoked - {key_id}")
            else:print(f"[WARN] Validation key cleanup returned {r.status_code}")
        except Exception as e:print(f"[WARN] Validation key cleanup failed: {type(e).__name__}")

    # The full scenario already verifies the workspace chain. The platform bootstrap key is
    # intentionally not used as a normal evidence-read credential.
    print("\nLOOPGRID v0.8 PILOT DEPLOYMENT VALIDATION: PASS")

if __name__=="__main__":main()
