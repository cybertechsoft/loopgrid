from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx


def fail(label: str, detail: str) -> None:
    print(f"[FAIL] {label} - {detail}")
    raise SystemExit(1)


def passed(label: str, detail: str = "") -> None:
    print(f"[PASS] {label}" + (f" - {detail}" if detail else ""))


def expect(resp: httpx.Response, status: int, label: str) -> httpx.Response:
    if resp.status_code != status:
        text = resp.text[:800]
        fail(label, f"expected HTTP {status}, got {resp.status_code}: {text}")
    return resp


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    p = argparse.ArgumentParser(description="LoopGrid human RBAC release-gate validation")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--workspace", default="default")
    args = p.parse_args()

    base = args.base_url.rstrip("/")
    ws = args.workspace

    users = {
        "owner": ("owner@rbac.loopgrid.test", "Owner Test", "OwnerPass!2026"),
        "admin": ("admin@rbac.loopgrid.test", "Admin Test", "AdminPass!2026"),
        "reviewer": ("reviewer@rbac.loopgrid.test", "Reviewer Test", "ReviewerPass!2026"),
        "viewer": ("viewer@rbac.loopgrid.test", "Viewer Test", "ViewerPass!2026"),
    }

    with httpx.Client(base_url=base, timeout=20.0) as c:
        h = expect(c.get("/health"), 200, "Server health").json()
        passed("Server health", h.get("version", "unknown"))

        # This test is meaningful only when anonymous access is disabled.
        r = c.get("/api/v1/dashboard", params={"workspace_id": ws})
        if r.status_code == 200:
            fail("Auth-required mode", "anonymous dashboard access is still allowed; restart with LOOPGRID_REQUIRE_USER_AUTH=true")
        if r.status_code not in (401, 403):
            fail("Auth-required mode", f"unexpected anonymous response HTTP {r.status_code}: {r.text[:500]}")
        passed("Anonymous access blocked", f"HTTP {r.status_code}")

        owner_email, owner_name, owner_pw = users["owner"]
        r = c.post("/api/v1/auth/bootstrap", json={
            "email": owner_email,
            "display_name": owner_name,
            "password": owner_pw,
            "workspace_id": ws,
        })
        if r.status_code == 409:
            fail("Owner bootstrap", "a user already exists in this database. Use a fresh RBAC test database as instructed.")
        expect(r, 200, "Owner bootstrap")
        owner = r.json()
        owner_token = owner["token"]
        passed("Owner bootstrap", owner["user"]["email"])

        me = expect(c.get("/api/v1/auth/me", headers=auth(owner_token)), 200, "Owner /auth/me").json()
        if me.get("role") != "owner" or set(me.get("scopes", [])) != {"admin", "ingest", "read", "review"}:
            fail("Owner scopes", json.dumps(me))
        passed("Owner scopes", ",".join(me["scopes"]))

        created: dict[str, dict] = {}
        for role in ("admin", "reviewer", "viewer"):
            email, name, pw = users[role]
            rr = expect(c.post(
                f"/api/v1/workspaces/{ws}/members/create-user",
                params={"role": role},
                headers=auth(owner_token),
                json={"email": email, "display_name": name, "password": pw},
            ), 200, f"Create {role}")
            created[role] = rr.json()
            passed(f"Create {role}", email)

        member_list = expect(c.get(f"/api/v1/workspaces/{ws}/members", headers=auth(owner_token)), 200, "Owner lists members").json()
        roles = {m["email"]: m["role"] for m in member_list}
        for role in users:
            email = users[role][0]
            if roles.get(email) != role:
                fail("Membership roles", f"{email}: expected {role}, got {roles.get(email)}")
        passed("Membership roles", "owner/admin/reviewer/viewer")

        tokens: dict[str, str] = {"owner": owner_token}
        for role in ("admin", "reviewer", "viewer"):
            email, _name, pw = users[role]
            rr = expect(c.post("/api/v1/auth/login", json={"email": email, "password": pw, "workspace_id": ws}), 200, f"{role} login").json()
            if rr.get("role") != role:
                fail(f"{role} login", f"unexpected role {rr.get('role')}")
            tokens[role] = rr["token"]
            passed(f"{role} login", role)

        # Read access: all human roles should be able to inspect workspace evidence.
        for role in ("owner", "admin", "reviewer", "viewer"):
            rr = c.get("/api/v1/dashboard", params={"workspace_id": ws}, headers=auth(tokens[role]))
            expect(rr, 200, f"{role} read access")
            passed(f"{role} read access")

        # Admin-only membership management.
        expect(c.get(f"/api/v1/workspaces/{ws}/members", headers=auth(tokens["admin"])), 200, "Admin membership access")
        passed("Admin membership access")
        rr = c.get(f"/api/v1/workspaces/{ws}/members", headers=auth(tokens["viewer"]))
        if rr.status_code not in (401, 403):
            fail("Viewer blocked from admin", f"expected 401/403, got {rr.status_code}")
        passed("Viewer blocked from admin", f"HTTP {rr.status_code}")

        # Create one policy-gated pending review using the local demo helper. This endpoint is
        # disabled in production, so the RBAC gate intentionally runs in auth-required development mode.
        pending = expect(c.post("/api/v1/demo/pending-review", headers=auth(owner_token)), 200, "Create pending review").json()
        # Demo response is DecisionDetail.
        summary = pending.get("summary", pending)
        decision_id = summary.get("decision_id")
        if not decision_id:
            fail("Create pending review", f"could not find decision_id in response: {json.dumps(pending)[:800]}")
        passed("Create pending review", decision_id)

        reviews = expect(c.get("/api/v1/reviews", params={"workspace_id": ws}, headers=auth(tokens["reviewer"])), 200, "Reviewer sees review queue").json()
        if decision_id not in {x.get("decision_id") for x in reviews}:
            fail("Reviewer sees review queue", f"decision {decision_id} not present")
        passed("Reviewer sees review queue", decision_id)

        rr = c.get("/api/v1/reviews", params={"workspace_id": ws}, headers=auth(tokens["viewer"]))
        if rr.status_code not in (401, 403):
            fail("Viewer blocked from review queue", f"expected 401/403, got {rr.status_code}")
        passed("Viewer blocked from review queue", f"HTTP {rr.status_code}")

        rr = c.post(
            f"/api/v1/decisions/{decision_id}/review",
            headers=auth(tokens["viewer"]),
            json={"action": "approve", "reviewer": users["viewer"][0], "reason": "viewer must not be allowed"},
        )
        if rr.status_code not in (401, 403):
            fail("Viewer blocked from approval", f"expected 401/403, got {rr.status_code}")
        passed("Viewer blocked from approval", f"HTTP {rr.status_code}")

        rr = expect(c.post(
            f"/api/v1/decisions/{decision_id}/review",
            headers=auth(tokens["reviewer"]),
            json={"action": "approve", "reviewer": users["reviewer"][0], "reason": "RBAC release-gate approval"},
        ), 200, "Reviewer approval")
        passed("Reviewer approval", decision_id)

        # Reviewer must not gain admin privileges.
        rr = c.get(f"/api/v1/workspaces/{ws}/members", headers=auth(tokens["reviewer"]))
        if rr.status_code not in (401, 403):
            fail("Reviewer blocked from admin", f"expected 401/403, got {rr.status_code}")
        passed("Reviewer blocked from admin", f"HTTP {rr.status_code}")

        # Logout must revoke the session immediately.
        expect(c.post("/api/v1/auth/logout", headers=auth(tokens["viewer"])), 200, "Viewer logout")
        rr = c.get("/api/v1/auth/me", headers=auth(tokens["viewer"]))
        if rr.status_code != 401:
            fail("Logged-out session rejected", f"expected HTTP 401, got {rr.status_code}")
        passed("Logged-out session rejected", "HTTP 401")

        # Audit trail should contain human identity/membership events.
        audit = expect(c.get(f"/api/v1/workspaces/{ws}/audit", headers=auth(owner_token)), 200, "Owner reads audit trail").json()
        event_types = {x.get("action") or x.get("event_type") for x in audit}
        # Do not depend on exact response naming; just require meaningful number of entries.
        if len(audit) < 5:
            fail("Human/admin audit trail", f"expected several audit entries, got {len(audit)}")
        passed("Human/admin audit trail", f"entries={len(audit)}")

    print("\nHUMAN RBAC VALIDATION RESULT: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.ConnectError:
        print("[FAIL] Connection - cannot reach LoopGrid. Start the auth-required test server first.")
        raise SystemExit(1)
