from __future__ import annotations
import argparse,base64,hashlib,json,subprocess,tempfile,zipfile
from pathlib import Path
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec,utils
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def canonical_json(obj)->bytes:
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")

def sha256_hex(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def _lines(z,name):
    try:return [json.loads(x) for x in z.read(name).decode().splitlines() if x.strip()]
    except KeyError:return []

def _json_file(z,name,default=None):
    try:return json.loads(z.read(name))
    except KeyError:return default

def _policy_digest(policy,workspace_id=None):
    if not isinstance(policy,dict):return None
    required={
        "workspace_id":policy.get("workspace_id") or workspace_id,
        "policy_id":policy.get("policy_id"),
        "version":policy.get("version"),
        "rule":policy.get("rule"),
    }
    return sha256_hex(canonical_json(required))


def _public_key_id(public)->str:
    if isinstance(public,Ed25519PublicKey):
        raw=public.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        return "ed25519:"+sha256_hex(raw)[:16]
    if isinstance(public,ec.EllipticCurvePublicKey):
        pem=public.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        return "aws-kms:"+sha256_hex(pem)[:16]
    return "unknown:"+sha256_hex(public.public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo))[:16]


def _verify_sig(public,algorithm,hex_hash,signature_b64):
    try:
        sig=base64.b64decode(signature_b64);digest=bytes.fromhex(hex_hash)
        if algorithm=="Ed25519":
            if not isinstance(public,Ed25519PublicKey):return False
            public.verify(sig,digest);return True
        if algorithm=="ECDSA_SHA_256":
            if not isinstance(public,ec.EllipticCurvePublicKey):return False
            public.verify(sig,digest,ec.ECDSA(utils.Prehashed(hashes.SHA256())));return True
        return False
    except Exception:return False


def _verify_rfc3161_imprint(raw: bytes, expected_digest: str) -> dict:
    """Validate RFC3161 status, SHA-256 algorithm and message imprint without OpenSSL."""
    try:
        from asn1crypto import tsp

        resp = tsp.TimeStampResp.load(raw)
        status = resp["status"]["status"].native
        if status not in {"granted", "granted_with_mods"}:
            return {"valid": False, "status": status, "reason": "timestamp_status_not_granted"}
        token = resp["time_stamp_token"]
        content = token["content"]["encap_content_info"]["content"]
        info = content.parsed
        imprint = info["message_imprint"]["hashed_message"].native.hex()
        algorithm = info["message_imprint"]["hash_algorithm"]["algorithm"].native
        valid = algorithm == "sha256" and imprint.lower() == expected_digest.lower()
        return {
            "valid": valid,
            "status": status,
            "algorithm": algorithm,
            "imprint": imprint,
            "gen_time": str(info["gen_time"].native),
        }
    except Exception as exc:
        return {"valid": False, "reason": "timestamp_parse_error", "detail": type(exc).__name__}


def _signed_body(e):
    return {k:e.get(k) for k in ["event_id","decision_id","workspace_id","event_type","occurred_at","actor","privacy_mode","payload_commitment","payload"]}


def verify_bundle(path:str,tsa_ca_file:str|None=None,expected_key_id:str|None=None,trusted_public_key:str|None=None)->dict:
    failures=[];warnings=[]
    with zipfile.ZipFile(path) as z:
        manifest=json.loads(z.read('manifest.json'))
        events=_lines(z,'events.jsonl');witnesses=_lines(z,'chain-witness.jsonl');disclosures=_lines(z,'disclosures.jsonl')
        signer_doc=_json_file(z,'signer.json')
        verification_doc=_json_file(z,'verification.json')
        lifecycle_doc=_json_file(z,'lifecycle.json')
        policy_doc=_json_file(z,'policy/policy.json')
        bundled_pem=z.read('public-key.pem');public=serialization.load_pem_public_key(bundled_pem)
        computed_key_id=_public_key_id(public);manifest_key_id=(manifest.get('signer') or {}).get('key_id') or (manifest.get('integrity') or {}).get('key_id')
        bundle_schema=manifest.get('bundle_schema')
        if bundle_schema and bundle_schema!='loopgrid/evidence-bundle/2':
            warnings.append({"reason":"unknown_bundle_schema","bundle_schema":bundle_schema})
        if signer_doc and signer_doc.get('key_id') and signer_doc.get('key_id')!=computed_key_id:
            failures.append({"reason":"signer_document_key_id_mismatch","signer_key_id":signer_doc.get('key_id'),"computed_key_id":computed_key_id})
        if lifecycle_doc is not None and manifest.get('lifecycle') is not None and lifecycle_doc!=manifest.get('lifecycle'):
            failures.append({"reason":"lifecycle_document_mismatch"})
        if verification_doc and verification_doc.get('decision_id') not in {None,manifest.get('decision_id')}:
            failures.append({"reason":"verification_document_decision_mismatch"})
        if policy_doc:
            digest=_policy_digest(policy_doc,manifest.get('workspace_id'))
            declared=policy_doc.get('policy_digest')
            manifest_digest=(manifest.get('policy') or {}).get('policy_digest')
            if declared and digest!=declared:
                failures.append({"reason":"policy_digest_mismatch","computed":digest,"declared":declared})
            if manifest_digest and digest!=manifest_digest:
                failures.append({"reason":"manifest_policy_digest_mismatch","computed":digest,"manifest":manifest_digest})
        if manifest_key_id and computed_key_id!=manifest_key_id:
            failures.append({"reason":"manifest_public_key_id_mismatch","manifest_key_id":manifest_key_id,"computed_key_id":computed_key_id})
        if expected_key_id and computed_key_id!=expected_key_id:
            failures.append({"reason":"expected_key_id_mismatch","expected_key_id":expected_key_id,"computed_key_id":computed_key_id})
        trusted_key_match=None
        if trusted_public_key:
            try:
                trusted=serialization.load_pem_public_key(Path(trusted_public_key).read_bytes())
                trusted_der=trusted.public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
                bundle_der=public.public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
                trusted_key_match=trusted_der==bundle_der
                if not trusted_key_match:failures.append({"reason":"trusted_public_key_mismatch"})
            except Exception as e:
                failures.append({"reason":"trusted_public_key_unreadable","detail":type(e).__name__})

        # Verify target events and opaque continuity witnesses in workspace-ledger order.
        nodes=[]
        for e in events:nodes.append({"seq":e['seq'],"event":e,"proof":e['proof'],"opaque":False})
        for w in witnesses:nodes.append({"seq":w['seq'],"event":None,"proof":w['proof'],"opaque":True})
        nodes.sort(key=lambda n:n['seq'])
        prev=None
        for node in nodes:
            proof=node['proof'];seq=node['seq'];alg=proof.get('signature_algorithm') or manifest.get('integrity',{}).get('signature_algorithm') or manifest.get('signer',{}).get('algorithm') or 'Ed25519'
            proof_key_id=proof.get('key_id')
            if proof_key_id and proof_key_id!=computed_key_id:
                failures.append({"seq":seq,"reason":"proof_key_id_mismatch","proof_key_id":proof_key_id,"computed_key_id":computed_key_id})
            if not node['opaque']:
                e=node['event'];expected_content=sha256_hex(canonical_json(_signed_body(e)))
                if expected_content!=proof.get('content_hash'):failures.append({"seq":seq,"reason":"content_hash_mismatch"})
                try:expected_chain=sha256_hex(bytes.fromhex(proof.get('previous_chain_hash','0'*64))+bytes.fromhex(expected_content))
                except Exception:
                    expected_chain='';failures.append({"seq":seq,"reason":"malformed_chain_hash"})
                if expected_chain!=proof.get('chain_hash'):failures.append({"seq":seq,"reason":"chain_hash_mismatch"})
            if prev is not None and proof.get('previous_chain_hash')!=prev:failures.append({"seq":seq,"reason":"previous_chain_hash_mismatch"})
            if not _verify_sig(public,alg,proof.get('chain_hash',''),proof.get('signature','')):failures.append({"seq":seq,"reason":"signature_invalid","algorithm":alg})
            prev=proof.get('chain_hash')

        # Verify optional full-payload disclosures against the commitments sealed in events.
        by_id={e['event_id']:e for e in events}
        for d in disclosures:
            e=by_id.get(d.get('event_id'))
            if not e:failures.append({"event_id":d.get('event_id'),"reason":"orphan_disclosure"});continue
            digest=sha256_hex(canonical_json(d.get('payload')))
            if digest!=e.get('payload_commitment') or digest!=d.get('payload_commitment'):failures.append({"event_id":d.get('event_id'),"reason":"disclosure_commitment_mismatch"})

        # Checkpoint proof + RFC3161 timestamp. Imprint validation is portable; optional
        # certificate-chain trust verification still uses OpenSSL when a CA bundle is supplied.
        cp=manifest.get('checkpoint') or {}
        checkpoint={"present":bool(cp),"signature_valid":None,"linked_to_bundle_chain":None}
        if cp:
            cp_digest=cp.get('chain_hash')
            cp_sig=cp.get('signature')
            cp_alg=cp.get('signature_algorithm') or manifest.get('signer',{}).get('algorithm')
            cp_key=cp.get('key_id')
            if cp_key and cp_key!=computed_key_id:
                failures.append({"reason":"checkpoint_key_id_mismatch","checkpoint_key_id":cp_key,"computed_key_id":computed_key_id})
            checkpoint['signature_valid']=bool(cp_digest and cp_sig and _verify_sig(public,cp_alg,cp_digest,cp_sig))
            if not checkpoint['signature_valid']:
                failures.append({"reason":"checkpoint_signature_invalid"})
            cp_seq=cp.get('ledger_seq')
            matched=next((n for n in nodes if n.get('seq')==cp_seq),None)
            checkpoint['linked_to_bundle_chain']=bool(matched and matched.get('proof',{}).get('chain_hash')==cp_digest)
            if not checkpoint['linked_to_bundle_chain']:
                warnings.append({"reason":"checkpoint_not_linked_to_bundle_chain","detail":"Bundle remains event-verifiable, but this checkpoint is not bridged by included nodes."})

        timestamp={"present":'timestamp.tsr' in z.namelist(),"imprint_valid":None,"trust_validated":None}
        if timestamp['present']:
            digest=cp.get('chain_hash') if cp else None
            if not digest:
                failures.append({"reason":"timestamp_checkpoint_missing"})
            else:
                imprint_result=_verify_rfc3161_imprint(z.read('timestamp.tsr'),digest)
                timestamp['imprint_valid']=imprint_result.get('valid') is True
                timestamp['status']=imprint_result.get('status')
                timestamp['algorithm']=imprint_result.get('algorithm')
                timestamp['gen_time']=imprint_result.get('gen_time')
                if not timestamp['imprint_valid']:
                    failures.append({"reason":"timestamp_imprint_invalid","detail":imprint_result.get('reason') or 'imprint mismatch'})

        if timestamp['present'] and tsa_ca_file:
            try:
                digest=cp.get('chain_hash')
                if not digest:raise ValueError('checkpoint chain hash missing')
                with tempfile.NamedTemporaryFile(suffix='.tsr',delete=False) as f:f.write(z.read('timestamp.tsr'));ts_path=f.name
                r=subprocess.run(['openssl','ts','-verify','-digest',digest,'-in',ts_path,'-CAfile',tsa_ca_file],capture_output=True,text=True,timeout=10)
                timestamp['trust_validated']=r.returncode==0
                if r.returncode!=0:failures.append({"reason":"timestamp_trust_invalid","detail":r.stderr[-300:]})
            except Exception as e:warnings.append({"reason":"timestamp_trust_not_checked","detail":type(e).__name__})
        elif timestamp['present']:
            warnings.append({"reason":"timestamp_present_trust_not_checked","detail":"RFC3161 imprint is valid; pass --tsa-ca-file for signer certificate-chain trust validation."})

        key_identity={
            "computed_key_id":computed_key_id,
            "manifest_key_id":manifest_key_id,
            "manifest_match":not manifest_key_id or computed_key_id==manifest_key_id,
            "expected_key_id":expected_key_id,
            "expected_key_match":None if expected_key_id is None else computed_key_id==expected_key_id,
            "trusted_public_key_supplied":bool(trusted_public_key),
            "trusted_public_key_match":trusted_key_match,
            "trust_note":"An embedded public key proves bundle integrity under that key. Pin --expected-key-id or --trusted-public-key when signer identity/authenticity must be established out of band."
        }
        return {"valid":not failures,"events":len(events),"witnesses":len(witnesses),"disclosures":len(disclosures),"failures":failures,"warnings":warnings,"decision_id":manifest.get('decision_id'),"workspace_id":manifest.get('workspace_id'),"software_version":manifest.get('software_version'),"evidence_profile":manifest.get('version'),"bundle_schema":manifest.get('bundle_schema') or 'legacy','signature_algorithm':manifest.get('signer',{}).get('algorithm') or manifest.get('integrity',{}).get('signature_algorithm'),"key_identity":key_identity,"checkpoint":checkpoint,"timestamp":timestamp,"lifecycle":manifest.get('lifecycle'),"policy_digest":(manifest.get('policy') or {}).get('policy_digest')}


def main():
    ap=argparse.ArgumentParser(description='Offline verifier for LoopGrid evidence bundles')
    ap.add_argument('bundle')
    ap.add_argument('--tsa-ca-file',default=None,help='Trusted CA bundle for RFC3161 signer validation via OpenSSL')
    ap.add_argument('--expected-key-id',default=None,help='Pin the expected LoopGrid signer key id, e.g. ed25519:abc123...')
    ap.add_argument('--trusted-public-key',default=None,help='Pin signer identity to an out-of-band trusted PEM public key')
    args=ap.parse_args();r=verify_bundle(args.bundle,args.tsa_ca_file,args.expected_key_id,args.trusted_public_key)
    # Keep CLI status text ASCII-only. On Windows, a verifier launched with stdout
    # redirected to a subprocess pipe may inherit a legacy code page that cannot
    # encode Unicode check/cross glyphs even though verification itself succeeded.
    print('LOOPGRID EVIDENCE VERIFICATION')
    print('[OK] VERIFIED' if r['valid'] else '[FAIL] INVALID')
    print(json.dumps(r,indent=2))
    raise SystemExit(0 if r['valid'] else 2)

if __name__=='__main__':main()
