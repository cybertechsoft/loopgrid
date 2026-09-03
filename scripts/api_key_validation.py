#!/usr/bin/env python3
"""External HTTP validation for LoopGrid v0.8 service API-key lifecycle.

Run against localhost after `python run.py`. In production/auth-required mode supply an
admin-capable key with --admin-key or LOOPGRID_ADMIN_KEY.
"""
from __future__ import annotations
import argparse, os, sys, uuid
import httpx


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}{' - ' + detail if detail else ''}")
    if not ok:
        raise RuntimeError(label + (": " + detail if detail else ""))


def main() -> None:
    ap = argparse.ArgumentParser(description="LoopGrid v0.8 API-key external validation")
    ap.add_argument("--base-url", default=os.getenv("LOOPGRID_BASE_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--workspace-id", default="default")
    ap.add_argument("--admin-key", default=os.getenv("LOOPGRID_ADMIN_KEY"))
    args = ap.parse_args()
    base=args.base_url.rstrip("/");wid=args.workspace_id;client=httpx.Client(timeout=20)

    def req(method,path,*,key=None,expected=None,**kw):
        headers=kw.pop("headers",{}).copy();use=key if key is not None else args.admin_key
        if use:headers["X-LoopGrid-Key"]=use
        r=client.request(method,base+path,headers=headers,**kw)
        if expected is None and r.status_code>=400:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
        if expected is not None and r.status_code!=expected:
            raise RuntimeError(f"{method} {path} expected {expected}, got {r.status_code}: {r.text[:500]}")
        return r

    health=req("GET","/health").json();check("Server health",health.get("ok") is True,health.get("version",""))

    # When no platform/admin key is supplied, local development bypass permits bootstrap issuance.
    admin=req("POST",f"/api/v1/workspaces/{wid}/keys",json={"name":"validation-admin","description":"temporary API-key validation admin","scopes":["admin"]}).json()
    admin_key=admin["api_key"]
    check("Admin service key issued",admin_key.startswith("lg_live_"),admin["key_id"])

    issued=req("POST",f"/api/v1/workspaces/{wid}/keys",key=admin_key,json={
        "name":"validation-ingest","description":"temporary validation agent","scopes":["ingest"],"expires_in_days":7
    }).json()
    old_key=issued["api_key"];old_id=issued["key_id"]
    check("Scoped ingest key issued",old_key.startswith("lg_live_"),old_id)

    run=uuid.uuid4().hex[:10]
    body={"workspace_id":wid,"decision_type":"api_key_validation","idempotency_key":f"key-validation:{run}:old","agent":{"id":"api-key-validation-agent"}}
    create=req("POST","/api/v1/decisions",key=old_key,json=body)
    check("Ingest scope can create decision",create.status_code==200,create.json()["decision_id"])

    denied=client.get(base+f"/api/v1/decisions?workspace_id={wid}",headers={"X-LoopGrid-Key":old_key})
    check("Ingest-only key cannot read",denied.status_code==401,f"HTTP {denied.status_code}")

    rotated=req("POST",f"/api/v1/workspaces/{wid}/keys/{old_id}/rotate",key=admin_key,json={"expires_in_days":30}).json()
    new_key=rotated["api_key"];new_id=rotated["new_key_id"]
    check("Replacement key issued",new_id!=old_id and new_key.startswith("lg_live_"),new_id)

    old_rejected=client.post(base+"/api/v1/decisions",headers={"X-LoopGrid-Key":old_key},json={"workspace_id":wid,"decision_type":"old_key_should_fail","agent":{"id":"a"}})
    check("Predecessor rejected immediately",old_rejected.status_code==401,f"HTTP {old_rejected.status_code}")

    new_accepted=req("POST","/api/v1/decisions",key=new_key,json={"workspace_id":wid,"decision_type":"rotated_key_works","idempotency_key":f"key-validation:{run}:new","agent":{"id":"a"}})
    check("Replacement key works",new_accepted.status_code==200,new_accepted.json()["decision_id"])

    rows=req("GET",f"/api/v1/workspaces/{wid}/keys",key=admin_key).json()
    old_meta=next(x for x in rows if x["key_id"]==old_id);new_meta=next(x for x in rows if x["key_id"]==new_id)
    check("Key metadata exposes lifecycle",old_meta["status"]=="revoked" and new_meta["status"]=="active" and new_meta["rotated_from_key_id"]==old_id)
    check("Expiry metadata present",bool(new_meta.get("expires_at")),new_meta.get("expires_at") or "")

    audit=req("GET",f"/api/v1/workspaces/{wid}/audit",key=admin_key).json()
    check("Rotation recorded in admin audit",any(x.get("action")=="api_key.rotated" and x.get("target_id")==new_id for x in audit))

    # Cleanup validation keys. The already-created evidence decisions intentionally remain append-only.
    req("DELETE",f"/api/v1/workspaces/{wid}/keys/{new_id}",key=admin_key)
    req("DELETE",f"/api/v1/workspaces/{wid}/keys/{admin['key_id']}",key=admin_key)
    print("\nAPI KEY VALIDATION RESULT: PASS")


if __name__=="__main__":
    try:main()
    except Exception as exc:
        print(f"\nAPI KEY VALIDATION RESULT: FAIL - {exc}",file=sys.stderr);raise SystemExit(1)
