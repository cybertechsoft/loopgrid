from __future__ import annotations
import io,json,zipfile,base64
from copy import deepcopy
from html import escape
from sqlalchemy import select
from sqlalchemy.orm import Session
from .ledger import verify_ledger,event_to_dict
from .models import LedgerEvent,PayloadBlob
from .service import get_events,summarize_decision,evidence_coverage
from .signing import signer
from .version import VERSION,EVIDENCE_PROFILE
from .checkpoints import latest_checkpoint_covering,checkpoint_to_dict


def _event_label(t):return t.replace('_',' ').title()

def render_report(summary,events,verification,coverage=None):
    coverage=coverage or evidence_coverage(summary,verification);action=summary.get('proposed_action') or {};policy=summary.get('policy') or {};outcome=summary.get('outcome') or {};agent=summary.get('agent') or {}
    def display_payload(e):
        if e.get('payload_available') is False:return {"payload":"encrypted disclosure unavailable or erased","commitment":e.get('payload_commitment'),"signed_descriptor":e.get('signed_payload') or e.get('payload')}
        return e.get('payload')
    rows=''.join(f"<tr><td>{e['seq']}</td><td>{escape(e['occurred_at'])}</td><td><b>{escape(_event_label(e['event_type']))}</b><small>{escape(e['actor']['type'])} · {escape(e['actor']['id'])}</small></td><td><pre>{escape(json.dumps(display_payload(e),ensure_ascii=False,indent=2)[:2600])}</pre></td></tr>" for e in events)
    def _check_html(c):
        st=c.get('status') or ('present' if c.get('present') else 'missing')
        cls='ok' if st=='present' else 'pending' if st=='pending' else 'na' if st=='not_applicable' else 'miss'
        icon='✓' if st=='present' else '…' if st=='pending' else '—' if st=='not_applicable' else '!'
        suffix=' · pending' if st=='pending' else ' · n/a' if st=='not_applicable' else ''
        return f"<span class='check {cls}'>{icon} {escape(c['label'])}{suffix}</span>"
    checks=''.join(_check_html(c) for c in coverage['checks']);status='VERIFIED' if verification['valid'] else 'INVALID'
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>LoopGrid evidence · {escape(summary['decision_id'])}</title><style>
:root{{--paper:#f4f1ea;--ink:#171816;--muted:#6b6c67;--line:#d6d2c9;--blue:#3157d5;--green:#146e5c;--red:#a43f44}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:14px/1.55 Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:1120px;margin:42px auto;padding:0 30px 70px}}header{{display:flex;justify-content:space-between;gap:30px;align-items:flex-start;border-top:4px solid var(--ink);padding-top:20px}}.brand{{font-weight:850;font-size:18px}}.kicker{{font:700 11px ui-monospace,monospace;color:var(--blue);letter-spacing:.08em;text-transform:uppercase;margin-top:36px}}h1,h2{{font-family:Georgia,"Times New Roman",serif;font-weight:500;letter-spacing:-.035em}}h1{{font-size:48px;line-height:1;margin:10px 0}}h2{{font-size:25px;margin:34px 0 12px}}.muted{{color:var(--muted)}}.badge{{border:1px solid var(--line);padding:9px 12px;font:750 12px ui-monospace,monospace;background:#fff}}.badge.ok{{color:var(--green);border-color:#9bc7bb}}.badge.bad{{color:var(--red);border-color:#d9a8ab}}.facts{{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);background:#fff;margin:30px 0}}.fact{{padding:18px;border-right:1px solid var(--line)}}.fact:last-child{{border-right:0}}.fact label{{display:block;font:700 10px ui-monospace,monospace;color:#85867f;text-transform:uppercase}}.fact strong{{display:block;font-family:Georgia,serif;font-size:19px;font-weight:500;margin-top:7px}}.coverage{{background:#fff;border:1px solid var(--line);padding:18px}}.score{{font-family:Georgia,serif;font-size:44px}}.checks{{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}}.check{{border:1px solid var(--line);padding:7px 9px;font-size:12px}}.check.ok{{color:var(--green)}}.check.pending{{color:#9b6b00;background:#fff9e8}}.check.na{{color:var(--muted);background:#f7f6f2}}.check.miss{{color:var(--red)}}table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line)}}th{{font:700 10px ui-monospace,monospace;text-transform:uppercase;letter-spacing:.06em;color:#85867f}}th,td{{text-align:left;vertical-align:top;padding:13px;border-bottom:1px solid var(--line)}}td small{{display:block;color:var(--muted);margin-top:3px}}pre{{margin:0;font:11px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;word-break:break-word}}.proof{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.proof pre{{background:#171816;color:#f5f2ea;padding:16px;min-height:150px}}footer{{border-top:1px solid var(--line);margin-top:34px;padding-top:14px;color:var(--muted);font-size:12px}}@media(max-width:760px){{.facts,.proof{{grid-template-columns:1fr}}.fact{{border-right:0;border-bottom:1px solid var(--line)}}h1{{font-size:38px}}}}</style></head><body><main><header><div><div class='brand'>LoopGrid</div><div class='kicker'>Decision evidence / evidence profile {escape(EVIDENCE_PROFILE)}</div><h1>Evidence record.</h1><div class='muted'>{escape(summary['decision_id'])} · {escape(summary.get('decision_type') or '')}</div></div><div class='badge {'ok' if verification['valid'] else 'bad'}'>{'✓' if verification['valid'] else '✕'} {status}</div></header><div class='facts'><div class='fact'><label>Agent</label><strong>{escape(str(agent.get('id','—')))}</strong></div><div class='fact'><label>Action</label><strong>{escape(str(action.get('tool','—')))}</strong></div><div class='fact'><label>Policy</label><strong>{escape(str(policy.get('version','—')))}</strong></div><div class='fact'><label>Outcome</label><strong>{escape(str(outcome.get('status','pending')).upper())}</strong></div></div><h2>Evidence state</h2><section class='coverage'><div class='score'>{coverage['score']}%</div><div><b>{escape(coverage.get('label','Evidence state'))}</b></div><div class='muted'>{coverage['passed']} of {coverage['total']} applicable controls captured<div class='checks'>{checks}</div></section><h2>Verification</h2><div class='proof'><pre>{escape(json.dumps(verification,indent=2))}</pre><pre>{escape(json.dumps({'privacy_mode':summary.get('privacy_mode'),'workspace_id':summary.get('workspace_id'),'payload_storage':'encrypted disclosure vault for FULL mode','independent_verification':'python loopgrid_verify.py evidence.zip','legal_note':'Integrity evidence is not by itself a legal compliance determination.'},indent=2))}</pre></div><h2>Append-only timeline</h2><table><thead><tr><th>#</th><th>Timestamp</th><th>Event</th><th>Evidence / disclosure</th></tr></thead><tbody>{rows}</tbody></table><footer>LoopGrid v{escape(VERSION)}. Verification confirms integrity of the captured record; it does not determine legal compliance.</footer></main></body></html>"""


def _signed_export_event(e:dict)->dict:
    out={k:deepcopy(v) for k,v in e.items() if k not in {"payload_available","payload_status","signed_payload"}}
    if "signed_payload" in e:out["payload"]=deepcopy(e["signed_payload"])
    return out

def _chain_witnesses(db, events, through_seq=None):
    if not events:
        return []
    lo = min(e["seq"] for e in events)
    event_hi = max(e["seq"] for e in events)
    hi = max(event_hi, int(through_seq or event_hi))
    target = {e["seq"] for e in events}
    rows = list(
        db.scalars(
            select(LedgerEvent)
            .where(
                LedgerEvent.workspace_id == events[0]["workspace_id"],
                LedgerEvent.seq >= lo,
                LedgerEvent.seq <= hi,
            )
            .order_by(LedgerEvent.seq.asc())
        )
    )
    return [
        {
            "seq": e.seq,
            "opaque": True,
            "proof": {
                "content_hash": e.content_hash,
                "previous_chain_hash": e.previous_chain_hash,
                "chain_hash": e.chain_hash,
                "signature": e.signature_b64,
                "key_id": e.key_id,
                "signature_algorithm": e.signature_algorithm,
            },
        }
        for e in rows
        if e.seq not in target
    ]

def build_bundle(db:Session,decision_id:str,*,include_payloads:bool=True):
    """Build Evidence Bundle v2 while preserving the v0.6-compatible core files.

    The bundle deliberately separates: signed ledger proof, human-readable decision
    projection, signer identity, policy provenance, lifecycle projection, and optional
    disclosure material. Third parties can therefore verify integrity without trusting
    the hosted LoopGrid UI or receiving raw FULL-mode payloads.
    """
    hydrated=get_events(db,decision_id)
    summary=summarize_decision(hydrated)
    verification=verify_ledger(db,decision_id)
    coverage=evidence_coverage(summary,verification)
    events=[_signed_export_event(e) for e in hydrated]
    lo=min(e['seq'] for e in events);hi=max(e['seq'] for e in events)
    # Only attach a checkpoint that was created at or after the decision's final event.
    # If it is later, include proof-only witnesses through the checkpoint head so the
    # portable bundle can independently link the decision chain to the timestamped head.
    cp=latest_checkpoint_covering(db,summary.get('workspace_id'),hi)
    witnesses=_chain_witnesses(db,events,through_seq=cp.ledger_seq if cp else None)

    disclosures=[]
    if include_payloads:
        for e in hydrated:
            if e.get("privacy_mode")=="full" and e.get("payload_available") is True:
                disclosures.append({"event_id":e["event_id"],"payload_commitment":e.get("payload_commitment"),"payload":e.get("payload")})

    cp_json=checkpoint_to_dict(cp) if cp else None
    policy=summary.get('policy') or None
    lifecycle=summary.get('lifecycle') or {}
    signer_json={
        **signer.posture(),
        "trust_model":"The embedded public key proves integrity under that key. Establish signer authenticity out of band with key-id or public-key pinning.",
        "public_key_file":"public-key.pem",
    }
    verification_json={
        "decision_id":decision_id,
        "workspace_id":summary.get('workspace_id'),
        "verified_at_export":verification.get('valid'),
        "integrity":verification,
        "coverage":coverage,
        "lifecycle":lifecycle,
        "offline_command":"python loopgrid_verify.py evidence.zip",
    }

    public_summary=summary if include_payloads else {
        "decision_id":decision_id,
        "workspace_id":summary.get("workspace_id"),
        "privacy_mode":summary.get("privacy_mode"),
        "created_at":summary.get("created_at"),
        "event_count":summary.get("event_count"),
        "decision_type":"withheld",
        "payload_disclosure":"withheld_by_export_option",
        "lifecycle":lifecycle,
    }
    manifest={
        "format":"LoopGrid Decision Evidence Bundle",
        "bundle_schema":"loopgrid/evidence-bundle/2",
        "version":EVIDENCE_PROFILE,
        "software_version":VERSION,
        "workspace_id":summary.get('workspace_id'),
        "privacy_mode":summary.get('privacy_mode','full'),
        "decision_id":decision_id,
        "decision_type":summary.get('decision_type') if include_payloads else None,
        "capture_source":(summary.get('metadata') or {}).get('capture_source') if include_payloads else None,
        "policy":{"id":policy.get('policy_id'),"version":policy.get('version'),"policy_digest":policy.get('policy_digest'),"input_commitment":policy.get('input_commitment')} if include_payloads and policy else None,
        "lifecycle":lifecycle,
        "event_count":len(events),
        "disclosure_count":len(disclosures),
        "payloads_included":bool(include_payloads),
        "ledger_span":{"first_seq":lo,"last_seq":hi,"witness_count":len(witnesses),"scope":"workspace-isolated chain segment"},
        "integrity":verification,
        "evidence_coverage":coverage,
        "signer":signer.posture(),
        "checkpoint":cp_json,
        "files":{
            "signed_events":"events.jsonl",
            "chain_witnesses":"chain-witness.jsonl",
            "signer":"signer.json",
            "verification":"verification.json",
            "lifecycle":"lifecycle.json",
            "policy":"policy/policy.json" if include_payloads and policy else None,
            "public_key":"public-key.pem",
            "report":"report.html",
            "disclosures":"disclosures.jsonl" if disclosures else None,
            "timestamp":"timestamp.tsr" if cp and cp.timestamp_token_b64 else None,
        },
        "independent_verification":"python loopgrid_verify.py evidence.zip",
        "cryptographic_profile":f"LoopGrid Evidence Profile {EVIDENCE_PROFILE}",
        "legal_note":"Evidence support only; not a legal compliance determination.",
    }

    # A disclosure-withheld export must not leak raw FULL payloads through report.html or
    # auxiliary JSON files. Policy metadata is withheld too because policy input fields can
    # reveal customer action details in custom policy systems.
    report_summary=summary if include_payloads else public_summary
    report_events=hydrated if include_payloads else events
    report=render_report(report_summary,report_events,verification,coverage)
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps(manifest,indent=2,ensure_ascii=False))
        z.writestr('decision.json',json.dumps(public_summary,indent=2,ensure_ascii=False))
        z.writestr('events.jsonl','\n'.join(json.dumps(e,ensure_ascii=False) for e in events))
        z.writestr('chain-witness.jsonl','\n'.join(json.dumps(w,ensure_ascii=False) for w in witnesses))
        z.writestr('signer.json',json.dumps(signer_json,indent=2,ensure_ascii=False))
        z.writestr('verification.json',json.dumps(verification_json,indent=2,ensure_ascii=False))
        z.writestr('lifecycle.json',json.dumps(lifecycle,indent=2,ensure_ascii=False))
        if include_payloads and policy:
            z.writestr('policy/policy.json',json.dumps(policy,indent=2,ensure_ascii=False))
        if disclosures:
            z.writestr('disclosures.jsonl','\n'.join(json.dumps(d,ensure_ascii=False) for d in disclosures))
        z.writestr('public-key.pem',signer.public_key_pem())
        z.writestr('report.html',report)
        if cp and cp.timestamp_token_b64:
            z.writestr('timestamp.tsr',base64.b64decode(cp.timestamp_token_b64))
        z.writestr('README.txt',
            'LoopGrid Evidence Bundle v2\n\n'
            'Verify integrity: python loopgrid_verify.py <bundle.zip>\n'
            'Pin signer identity: python loopgrid_verify.py <bundle.zip> --expected-key-id <key-id>\n'
            'or: python loopgrid_verify.py <bundle.zip> --trusted-public-key <public.pem>\n\n'
            'No LoopGrid server connection is required. The embedded public key proves integrity under that key; '\
            'signer authenticity should be pinned out-of-band for high-assurance use.\n'
            'FULL mode raw payloads are encrypted outside the signed ledger; disclosures.jsonl is optional and commitment-checked.\n'
            'chain-witness.jsonl contains proof-only bridge nodes and no unrelated decision payloads.\n'
            'verification.json records export-time server verification; always run the offline verifier independently when relying on the evidence.\n'
        )
    return buf.getvalue(),f"loopgrid-evidence-{decision_id}.zip"
