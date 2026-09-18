import os, tempfile, atexit
from pathlib import Path

TMP=tempfile.TemporaryDirectory()
os.environ['LOOPGRID_DATABASE_URL']=f"sqlite:///{Path(TMP.name)/'test.db'}"
os.environ['LOOPGRID_SIGNING_KEY_PATH']=str(Path(TMP.name)/'key.pem')
os.environ['LOOPGRID_PUBLIC_KEY_PATH']=str(Path(TMP.name)/'pub.pem')
os.environ['LOOPGRID_PAYLOAD_KEY_PATH']=str(Path(TMP.name)/'payload-key.bin')
os.environ['LOOPGRID_ENV']='development'
os.environ.pop('LOOPGRID_TSA_URL', None)
os.environ.pop('LOOPGRID_TSA_CA_FILE', None)

from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.db import engine
atexit.register(engine.dispose)
from verifier.loopgrid_verify import verify_bundle

client=TestClient(app)

def reset():
    r=client.delete('/api/v1/demo/reset')
    assert r.status_code==200


def test_demo_end_to_end(tmp_path):
    reset()
    r=client.post('/api/v1/demo/refund'); assert r.status_code==200
    did=r.json()['summary']['decision_id']
    assert r.json()['verification']['valid'] is True
    assert r.json()['summary']['outcome']['status']=='succeeded'
    assert r.json()['coverage']['score']==100

    replay=client.post(f'/api/v1/decisions/{did}/replay',json={'mode':'policy','policy_threshold':1000})
    assert replay.status_code==200
    assert replay.json()['counterfactual']['decision']=='auto_allowed'
    assert replay.json()['changed'] is True

    ev=client.get(f'/api/v1/decisions/{did}/evidence'); assert ev.status_code==200
    p=tmp_path/'evidence.zip'; p.write_bytes(ev.content)
    result=verify_bundle(str(p)); assert result['valid'] is True

    report=client.get(f'/api/v1/decisions/{did}/report')
    assert report.status_code==200
    assert 'Evidence state' in report.text


def test_demo_workspace_scenarios():
    reset()
    r=client.post('/api/v1/demo/workspace'); assert r.status_code==200
    assert r.json()['count']==3
    decisions=client.get('/api/v1/decisions').json()
    assert len(decisions)==3
    policy_results={(d.get('policy') or {}).get('decision') for d in decisions}
    assert {'auto_allowed','human_approval_required','blocked'} <= policy_results
    dash=client.get('/api/v1/dashboard').json()
    assert dash['decisions']==3
    assert dash['human_approvals']==1
    assert dash['policy_blocks']==1
    assert dash['outcome_verified']==3


def test_safe_tamper_lab_does_not_modify_production():
    reset()
    r=client.post('/api/v1/demo/refund'); did=r.json()['summary']['decision_id']
    before=client.get(f'/api/v1/decisions/{did}/verify').json()
    t=client.post(f'/api/v1/decisions/{did}/tamper-test').json()
    after=client.get(f'/api/v1/decisions/{did}/verify').json()
    assert t['production_record_unchanged'] is True
    assert t['simulated_tamper']['detected'] is True
    assert 'content_hash_mismatch' in t['simulated_tamper']['reasons']
    assert before['valid'] is True and after['valid'] is True


def test_database_tamper_detection():
    reset()
    r=client.post('/api/v1/demo/refund'); did=r.json()['summary']['decision_id']
    with engine.begin() as conn:
        conn.execute(text("UPDATE ledger_events SET payload_json='{}' WHERE decision_id=:d AND event_type='model_completed'"), {'d':did})
    v=client.get('/api/v1/integrity/verify').json()
    assert v['valid'] is False
    assert any('content_hash_mismatch' in f.get('reasons',[]) for f in v['failures'])


def test_post_replay_export_with_interleaved_workspace_events(tmp_path):
    """Regression: per-decision export must remain independently verifiable after replay.

    The demo workspace creates three decisions in a shared global chain. Replaying the
    middle decision appends its replay after events from the third decision, so the
    evidence bundle needs proof-only chain witnesses for the intervening records.
    """
    reset()
    r=client.post('/api/v1/demo/workspace'); assert r.status_code==200
    did=r.json()['created'][1]
    replay=client.post(f'/api/v1/decisions/{did}/replay',json={'mode':'policy','policy_threshold':1000})
    assert replay.status_code==200 and replay.json()['changed'] is True

    ev=client.get(f'/api/v1/decisions/{did}/evidence'); assert ev.status_code==200
    p=tmp_path/'post-replay-evidence.zip'; p.write_bytes(ev.content)
    result=verify_bundle(str(p))
    assert result['valid'] is True
    assert result['events']==7
    assert result['witnesses']>0


def test_workspace_keys_and_isolated_chains():
    reset()
    w1=client.post('/api/v1/workspaces',json={'name':'Fintech A','privacy_mode':'full'}).json()
    w2=client.post('/api/v1/workspaces',json={'name':'Fintech B','privacy_mode':'full'}).json()
    k1=client.post(f"/api/v1/workspaces/{w1['workspace_id']}/keys",json={'name':'ingest'}).json()['api_key']
    k2=client.post(f"/api/v1/workspaces/{w2['workspace_id']}/keys",json={'name':'ingest'}).json()['api_key']
    d1=client.post('/api/v1/decisions',headers={'X-LoopGrid-Key':k1},json={'workspace_id':w1['workspace_id'],'decision_type':'payment','agent':{'id':'a1'}}); assert d1.status_code==200
    d2=client.post('/api/v1/decisions',headers={'X-LoopGrid-Key':k2},json={'workspace_id':w2['workspace_id'],'decision_type':'claim','agent':{'id':'a2'}}); assert d2.status_code==200
    v1=client.get('/api/v1/integrity/verify',params={'workspace_id':w1['workspace_id']}).json()
    v2=client.get('/api/v1/integrity/verify',params={'workspace_id':w2['workspace_id']}).json()
    assert v1['valid'] and v2['valid'] and v1['total_ledger_events']==1 and v2['total_ledger_events']==1
    assert d1.json()['event']['proof']['previous_chain_hash']=='0'*64
    assert d2.json()['event']['proof']['previous_chain_hash']=='0'*64


def test_idempotency_prevents_duplicate_decisions():
    reset()
    body={'workspace_id':'default','decision_type':'refund','idempotency_key':'req:abc','agent':{'id':'agent'}}
    a=client.post('/api/v1/decisions',json=body).json(); b=client.post('/api/v1/decisions',json=body).json()
    assert a['decision_id']==b['decision_id']
    assert b.get('idempotent_replay') is True
    assert client.get('/api/v1/dashboard').json()['decisions']==1


def test_redacted_and_proof_only_privacy_modes():
    reset()
    red=client.post('/api/v1/decisions',json={'workspace_id':'default','privacy_mode':'redacted','decision_type':'support','agent':{'id':'agent'},'input':{'message':'secret customer text','ticket_id':'T-1'}}).json()
    ev=red['event']; raw=str(ev['payload'])
    assert 'secret customer text' not in raw and ev['payload_commitment']
    assert ev['payload']['input']['message']['redacted'] is True
    proof=client.post('/api/v1/decisions',json={'workspace_id':'default','privacy_mode':'proof_only','decision_type':'support','agent':{'id':'agent'},'input':{'message':'never store me'}}).json()['event']
    assert proof['payload']=={'proof_only':True,'payload_sha256':proof['payload_commitment']}
    assert 'never store me' not in str(proof)


def test_otel_ingestion_and_checkpoint():
    reset()
    payload={'workspace_id':'default','spans':[{'trace_id':'trace-1','span_id':'span-1','name':'chat.completions','attributes':{'service.name':'refund-agent','gen_ai.provider.name':'openai','gen_ai.request.model':'gpt-5','loopgrid.decision.type':'refund_assessment'}}]}
    r=client.post('/api/v1/ingest/otel',json=payload); assert r.status_code==200 and r.json()['accepted']==1
    r2=client.post('/api/v1/ingest/otel',json=payload); assert r2.status_code==200
    assert r.json()['decision_ids'][0]==r2.json()['decision_ids'][0]
    assert client.get('/api/v1/dashboard').json()['decisions']==1
    cp=client.post('/api/v1/workspaces/default/checkpoint',json={}).json()
    assert cp['chain_hash'] and cp['signature'] and cp['external_timestamp'] is False


def test_workspace_isolated_export_survives_global_seq_gaps(tmp_path):
    reset()
    w1=client.post('/api/v1/workspaces',json={'name':'Workspace One','privacy_mode':'full'}).json()['workspace_id']
    w2=client.post('/api/v1/workspaces',json={'name':'Workspace Two','privacy_mode':'full'}).json()['workspace_id']
    a=client.post('/api/v1/decisions',json={'workspace_id':w1,'decision_type':'a','agent':{'id':'a'}}).json()['decision_id']
    client.post('/api/v1/decisions',json={'workspace_id':w2,'decision_type':'b','agent':{'id':'b'}})
    client.post(f'/api/v1/decisions/{a}/events',json={'event_type':'outcome_observed','actor_type':'system','actor_id':'verify','payload':{'status':'succeeded'}})
    bundle=client.get(f'/api/v1/decisions/{a}/evidence'); assert bundle.status_code==200
    p=tmp_path/'isolated.zip'; p.write_bytes(bundle.content)
    result=verify_bundle(str(p))
    assert result['valid'] is True

def test_policy_registry_and_versioned_evaluation():
    reset(); policies=client.get('/api/v1/workspaces/default/policies').json(); assert any(p['policy_id']=='refund-policy' and p['active'] for p in policies)
    r=client.post('/api/v1/workspaces/default/policies',json={'policy_id':'refund-policy','name':'Refund authority','version':'18.0','rule':{'type':'amount_threshold','field':'amount','auto_approve_max':900,'hard_limit':2000,'currency':'USD'},'active':True}); assert r.status_code==200
    e=client.post('/api/v1/workspaces/default/policies/evaluate',json={'policy_id':'refund-policy','proposed_action':{'amount':720},'authority':{'limit_usd':2000}}); assert e.status_code==200 and e.json()['decision']=='auto_allowed' and e.json()['version']=='18.0'

def test_pending_review_queue_and_human_review():
    reset(); r=client.post('/api/v1/demo/pending-review'); assert r.status_code==200; did=r.json()['summary']['decision_id']
    q=client.get('/api/v1/reviews').json(); assert any(x['decision_id']==did for x in q)
    rv=client.post(f'/api/v1/decisions/{did}/review',json={'action':'approve','reviewer':'risk@acme.example','reason':'Validated duplicate charge'}); assert rv.status_code==200
    assert not any(x['decision_id']==did for x in client.get('/api/v1/reviews').json())
    assert client.get(f'/api/v1/decisions/{did}').json()['summary']['approval']['reviewer']=='risk@acme.example'

def test_scoped_api_key_enforcement_and_revocation():
    reset(); k=client.post('/api/v1/workspaces/default/keys',json={'name':'ingest-only','scopes':['ingest']}).json(); raw=k['api_key']
    assert client.post('/api/v1/decisions',headers={'X-LoopGrid-Key':raw},json={'workspace_id':'default','decision_type':'x','agent':{'id':'a'}}).status_code==200
    assert client.get('/api/v1/decisions?workspace_id=default',headers={'X-LoopGrid-Key':raw}).status_code==401
    assert client.delete(f"/api/v1/workspaces/default/keys/{k['key_id']}").status_code==200
    assert client.post('/api/v1/decisions',headers={'X-LoopGrid-Key':raw},json={'workspace_id':'default','decision_type':'y','agent':{'id':'a'}}).status_code==401

def test_custom_redaction_fields():
    reset(); client.patch('/api/v1/workspaces/default',json={'redaction_fields':['metadata.internal_case_id']})
    d=client.post('/api/v1/decisions',json={'workspace_id':'default','privacy_mode':'redacted','decision_type':'case','agent':{'id':'a'},'metadata':{'internal_case_id':'CASE-SECRET','public_label':'ok'}}).json(); payload=d['event']['payload']
    assert payload['metadata']['internal_case_id']['redacted'] is True and 'CASE-SECRET' not in str(payload) and payload['metadata']['public_label']=='ok'

def test_mcp_jsonrpc_ingestion():
    reset(); body={'workspace_id':'default','trace_id':'tr-mcp-1','agent_id':'ops-agent','server_name':'billing-mcp','request':{'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'refund','arguments':{'amount':20}}},'response':{'jsonrpc':'2.0','id':1,'result':{'ok':True}}}
    r=client.post('/api/v1/ingest/mcp',json=body); assert r.status_code==200; d=client.get(f"/api/v1/decisions/{r.json()['decision_id']}").json(); assert d['summary']['metadata']['source']=='mcp-json-rpc' and d['summary']['outcome']['status']=='succeeded' and any(e['event_type']=='mcp_tool_requested' for e in d['events'])

def test_otlp_http_json_receiver():
    reset(); otlp={'resourceSpans':[{'resource':{'attributes':[{'key':'service.name','value':{'stringValue':'agent-api'}}]},'scopeSpans':[{'scope':{'name':'openai.instrumentation'},'spans':[{'traceId':'abc','spanId':'def','name':'chat','attributes':[{'key':'gen_ai.provider.name','value':{'stringValue':'openai'}},{'key':'gen_ai.request.model','value':{'stringValue':'gpt-test'}}]}]}]}]}
    r=client.post('/v1/traces',headers={'X-LoopGrid-Workspace':'default','Content-Type':'application/json'},content=__import__('json').dumps(otlp).encode()); assert r.status_code==200 and r.headers['x-loopgrid-accepted']=='1' and r.json()=={}
    d=client.get('/api/v1/decisions').json()[0]; assert d['model']['provider']=='openai' and d['model']['name']=='gpt-test' and d['metadata']['source']=='otlp-http-json'

def test_audit_log_and_operational_endpoints():
    reset(); client.post('/api/v1/workspaces/default/keys',json={'name':'audit-test','scopes':['ingest','read']}); logs=client.get('/api/v1/workspaces/default/audit').json(); assert any(x['action']=='api_key.created' for x in logs)
    assert client.get('/ready').json()['ready'] is True; m=client.get('/metrics'); assert m.status_code==200 and 'loopgrid_decisions_total' in m.text

def test_security_headers_and_request_id():
    r=client.get('/health',headers={'X-Request-ID':'req-test-123'}); assert r.status_code==200 and r.headers['x-request-id']=='req-test-123' and r.headers['x-content-type-options']=='nosniff' and r.headers['x-frame-options']=='DENY'

def test_demo_reset_restores_baseline_policy():
    reset()
    client.post('/api/v1/workspaces/default/policies',json={'policy_id':'refund-policy','name':'Refund authority','version':'99.0','rule':{'type':'amount_threshold','field':'amount','auto_approve_max':999,'hard_limit':3000},'active':True})
    rr=client.delete('/api/v1/demo/reset'); assert rr.status_code==200
    p=client.get('/api/v1/workspaces/default/policies').json(); active=[x for x in p if x['active']]
    assert len(active)==1 and active[0]['version']=='17.3' and active[0]['rule']['auto_approve_max']==500


def test_v07_system_info_and_openapi_contract():
    info=client.get('/api/v1/system/info');assert info.status_code==200
    j=info.json();assert j['version'].startswith('0.8.1') and j['evidence_profile']=='3.0-draft'
    assert j['payload_vault']['algorithm']=='AES-256-GCM' and j['payload_vault']['erasable_without_breaking_chain'] is True
    schema=client.get('/openapi.json').json();schemes=schema['components']['securitySchemes']
    assert 'LoopGridApiKey' in schemes and 'LoopGridUserBearer' in schemes
    dash_schema=schema['paths']['/api/v1/dashboard']['get']['responses']['200']['content']['application/json']['schema']
    assert '$ref' in dash_schema and 'DashboardResponse' in dash_schema['$ref']
    assert schema['paths']['/api/v1/decisions']['post']['security']


def test_full_payload_encrypted_outside_signed_ledger_and_erasure_preserves_proof(tmp_path):
    reset();secret='customer-secret-DO-NOT-STORE-IN-LEDGER'
    r=client.post('/api/v1/decisions',json={'workspace_id':'default','privacy_mode':'full','decision_type':'support_case','agent':{'id':'agent-1'},'input':{'message':secret}});assert r.status_code==200;did=r.json()['decision_id']
    assert secret in str(r.json()['event']['payload'])
    with engine.begin() as conn:
        ledger=conn.execute(text("SELECT payload_json FROM ledger_events WHERE decision_id=:d"),{'d':did}).scalar_one()
        blob=conn.execute(text("SELECT ciphertext_b64 FROM payload_blobs WHERE event_id=(SELECT event_id FROM ledger_events WHERE decision_id=:d LIMIT 1)"),{'d':did}).scalar_one()
    assert secret not in ledger and secret not in blob and 'payload_ref' in ledger
    bundle=client.get(f'/api/v1/decisions/{did}/evidence');p=tmp_path/'with-disclosure.zip';p.write_bytes(bundle.content);vr=verify_bundle(str(p));assert vr['valid'] and vr['disclosures']==1
    er=client.post(f'/api/v1/decisions/{did}/payload/erase',json={'reason':'customer_request'});assert er.status_code==200 and er.json()['erased_payloads']==1 and er.json()['ledger_integrity_valid'] is True
    detail=client.get(f'/api/v1/decisions/{did}').json();created=detail['events'][0];assert created['payload_available'] is False and secret not in str(created)
    p2=tmp_path/'after-erasure.zip';p2.write_bytes(client.get(f'/api/v1/decisions/{did}/evidence').content);vr2=verify_bundle(str(p2));assert vr2['valid'] and vr2['disclosures']==0


def test_evidence_export_can_withhold_full_disclosures(tmp_path):
    reset();secret='withhold-this-payload'
    did=client.post('/api/v1/decisions',json={'workspace_id':'default','privacy_mode':'full','decision_type':'sensitive','agent':{'id':'a'},'input':{'message':secret}}).json()['decision_id']
    r=client.get(f'/api/v1/decisions/{did}/evidence?include_payloads=false');assert r.status_code==200
    p=tmp_path/'no-disclosures.zip';p.write_bytes(r.content);v=verify_bundle(str(p));assert v['valid'] and v['disclosures']==0
    import zipfile
    with zipfile.ZipFile(p) as z:
        combined=b'\n'.join(z.read(n) for n in z.namelist() if n.endswith(('.json','.jsonl','.txt','.html')))
        assert secret.encode() not in combined and 'disclosures.jsonl' not in z.namelist()


def test_retention_run_erases_expired_disclosures_without_chain_break():
    reset();did=client.post('/api/v1/decisions',json={'workspace_id':'default','privacy_mode':'full','decision_type':'retention','agent':{'id':'a'},'input':{'message':'expire me'}}).json()['decision_id']
    with engine.begin() as conn:conn.execute(text("UPDATE payload_blobs SET expires_at='2000-01-01 00:00:00' WHERE workspace_id='default'"))
    r=client.post('/api/v1/workspaces/default/retention/run',json={});assert r.status_code==200 and r.json()['erased_payloads']>=1 and r.json()['ledger_integrity_valid'] is True
    assert client.get('/api/v1/integrity/verify').json()['valid'] is True


def test_checkpoint_is_persisted_and_exported(tmp_path):
    reset();did=client.post('/api/v1/demo/refund').json()['summary']['decision_id'];cp=client.post('/api/v1/workspaces/default/checkpoint',json={}).json();assert cp['checkpoint_id'] and cp['chain_hash'] and cp['signature_algorithm']
    ev=client.get(f'/api/v1/decisions/{did}/evidence');p=tmp_path/'checkpoint.zip';p.write_bytes(ev.content)
    import zipfile,json
    with zipfile.ZipFile(p) as z:manifest=json.loads(z.read('manifest.json'))
    assert manifest['checkpoint']['checkpoint_id']==cp['checkpoint_id'] and manifest['software_version'].startswith('0.8.1') and manifest['version']=='3.0-draft'


def test_human_rbac_bearer_sessions_and_roles():
    reset()
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM user_sessions'));conn.execute(text('DELETE FROM workspace_memberships'));conn.execute(text('DELETE FROM user_accounts'))
    b=client.post('/api/v1/auth/bootstrap',json={'email':'owner@example.com','display_name':'Owner','password':'very-secure-password','workspace_id':'default'});assert b.status_code==200;owner=b.json()['token']
    oh={'Authorization':f'Bearer {owner}'}
    me=client.get('/api/v1/auth/me',headers=oh);assert me.status_code==200 and me.json()['role']=='owner' and 'admin' in me.json()['scopes']
    u=client.post('/api/v1/workspaces/default/members/create-user?role=reviewer',headers=oh,json={'email':'reviewer@example.com','display_name':'Reviewer','password':'reviewer-secure-password'});assert u.status_code==200
    login=client.post('/api/v1/auth/login',json={'email':'reviewer@example.com','password':'reviewer-secure-password','workspace_id':'default'});assert login.status_code==200;reviewer=login.json()['token'];rh={'Authorization':f'Bearer {reviewer}'}
    assert client.get('/api/v1/decisions?workspace_id=default',headers=rh).status_code==200
    assert client.post('/api/v1/workspaces/default/policies',headers=rh,json={'policy_id':'x','name':'x','version':'1','rule':{},'active':True}).status_code==401
    pending=client.post('/api/v1/demo/pending-review').json()['summary']['decision_id']
    assert client.post(f'/api/v1/decisions/{pending}/review',headers=rh,json={'action':'approve','reviewer':'reviewer@example.com','reason':'checked'}).status_code==200
    assert client.post('/api/v1/auth/logout',headers=rh).status_code==200
    assert client.get('/api/v1/auth/me',headers=rh).status_code==401


def test_mcp_proxy_rejects_arbitrary_unconfigured_targets():
    reset();r=client.post('/api/v1/mcp-proxy/not-configured',json={'jsonrpc':'2.0','id':1,'method':'tools/list'});assert r.status_code==404 and 'arbitrary URLs' in r.text


def test_sdk_integrations_capture_usage_latency_and_tool_requests():
    import sys
    root=str(Path(__file__).resolve().parents[1]/'sdk'/'python')
    if root not in sys.path:sys.path.insert(0,root)
    from loopgrid.integrations.openai import OpenAIRecorder
    from loopgrid.integrations.anthropic import AnthropicRecorder
    class Grid:
        def __init__(self):self.events=[]
        def record_decision(self,**kw):self.start=kw;return {'decision_id':'d1'}
        def add_event(self,did,event_type,payload,**kw):self.events.append((event_type,payload,kw))
    class Obj:pass
    g=Grid();msg=Obj();msg.content='ok';fn=Obj();fn.name='refund';fn.arguments='{"amount": 20}';call=Obj();call.id='tc1';call.function=fn;msg.tool_calls=[call];choice=Obj();choice.message=msg;choice.finish_reason='tool_calls';usage=Obj();usage.prompt_tokens=10;usage.completion_tokens=4;usage.total_tokens=14;resp=Obj();resp.id='req1';resp.choices=[choice];resp.usage=usage
    class ChatCompletions:
        def create(self,**kwargs):return resp
    class Chat:completions=ChatCompletions()
    class OAI:chat=Chat()
    OpenAIRecorder(g,OAI()).chat_completions_create(model='gpt-test',messages=[{'role':'user','content':'refund'}])
    assert g.events[0][0]=='model_completed' and g.events[0][1]['usage']['total_tokens']==14 and 'latency_ms' in g.events[0][1]
    assert any(e[0]=='tool_requested' and e[1]['name']=='refund' for e in g.events)
    g2=Grid();block=Obj();block.type='tool_use';block.id='tu1';block.name='lookup';block.input={'id':1};ar=Obj();ar.id='a1';ar.content=[block];ar.usage=Obj();ar.usage.input_tokens=5;ar.usage.output_tokens=3;ar.stop_reason='tool_use'
    class Messages:
        def create(self,**kwargs):return ar
    class Anth:messages=Messages()
    AnthropicRecorder(g2,Anth()).messages_create(model='claude-test',messages=[])
    assert any(e[0]=='tool_requested' and e[1]['name']=='lookup' for e in g2.events)

def test_offline_verifier_can_pin_signer_identity(tmp_path):
    reset(); client.post('/api/v1/demo/workspace')
    did=client.get('/api/v1/decisions').json()[0]['decision_id']
    bundle=client.get(f'/api/v1/decisions/{did}/evidence').content
    p=tmp_path/'evidence.zip';p.write_bytes(bundle)
    from verifier.loopgrid_verify import verify_bundle
    good=verify_bundle(str(p))
    key_id=good['key_identity']['computed_key_id']
    assert good['valid'] is True
    assert verify_bundle(str(p),expected_key_id=key_id)['valid'] is True
    bad=verify_bundle(str(p),expected_key_id='ed25519:'+'0'*16)
    assert bad['valid'] is False
    assert any(x['reason']=='expected_key_id_mismatch' for x in bad['failures'])


def test_v07_lifecycle_coverage_marks_pending_not_missing():
    reset();r=client.post('/api/v1/demo/pending-review');did=r.json()['summary']['decision_id'];c=client.get(f'/api/v1/decisions/{did}').json()['coverage']
    assert c['state']=='awaiting_human_review' and c['complete'] is False and c['pending']>=1 and c['missing']==0
    st={x['id']:x['status'] for x in c['checks']};assert st['human_oversight']=='pending' and st['action']=='pending' and st['outcome']=='pending'

def test_v07_dashboard_separates_completed_and_pending_reviews():
    reset();client.post('/api/v1/demo/workspace');client.post('/api/v1/demo/pending-review');d=client.get('/api/v1/dashboard').json();assert d['completed_reviews']==1 and d['human_approvals']==1 and d['human_rejections']==0 and d['pending_reviews']==1

def test_v07_pilot_readiness_endpoint_discloses_gaps():
    r=client.get('/api/v1/pilot/readiness');assert r.status_code==200;j=r.json();assert j['version'].startswith('0.8.1') and j['controlled_pilot_ready'] is True
    ids={x['id']:x for x in j['checks']};assert ids['database']['status']=='pass' and ids['signed_ledger']['status']=='pass' and ids['payload_vault']['status']=='pass';assert 'signer_boundary' in ids and 'external_timestamp' in ids and 'database_topology' in ids


# ---------------------------------------------------------------------------
# v0.8 Design Partner Release regression gates
# ---------------------------------------------------------------------------

def test_v07_api_key_expiry_metadata_and_rejection():
    reset()
    issued=client.post('/api/v1/workspaces/default/keys',json={
        'name':'short-lived','description':'temporary integration key','scopes':['ingest'],
        'expires_in_days':1,
    })
    assert issued.status_code==200
    key_id=issued.json()['key_id'];raw=issued.json()['api_key']
    listed=client.get('/api/v1/workspaces/default/keys').json()
    meta=next(k for k in listed if k['key_id']==key_id)
    assert meta['description']=='temporary integration key' and meta['status']=='active' and meta['expires_at']
    with engine.begin() as conn:
        conn.execute(text("UPDATE api_keys SET expires_at='2000-01-01 00:00:00' WHERE key_id=:k"),{'k':key_id})
    denied=client.post('/api/v1/decisions',headers={'X-LoopGrid-Key':raw},json={'workspace_id':'default','decision_type':'expired','agent':{'id':'a'}})
    assert denied.status_code==401
    listed2=client.get('/api/v1/workspaces/default/keys').json();meta2=next(k for k in listed2 if k['key_id']==key_id)
    assert meta2['expired'] is True and meta2['status']=='expired'


def test_v07_api_key_rotation_revokes_predecessor_atomically():
    reset()
    admin=client.post('/api/v1/workspaces/default/keys',json={'name':'admin','scopes':['admin']}).json()['api_key']
    ah={'X-LoopGrid-Key':admin}
    issued=client.post('/api/v1/workspaces/default/keys',headers=ah,json={'name':'agent-ingest','description':'refund agent','scopes':['ingest']}).json()
    old=issued['api_key'];old_id=issued['key_id']
    rotated=client.post(f'/api/v1/workspaces/default/keys/{old_id}/rotate',headers=ah,json={'expires_in_days':30})
    assert rotated.status_code==200
    new=rotated.json()['api_key'];new_id=rotated.json()['new_key_id']
    denied=client.post('/api/v1/decisions',headers={'X-LoopGrid-Key':old},json={'workspace_id':'default','decision_type':'old-key','agent':{'id':'a'}})
    accepted=client.post('/api/v1/decisions',headers={'X-LoopGrid-Key':new},json={'workspace_id':'default','decision_type':'new-key','agent':{'id':'a'}})
    assert denied.status_code==401 and accepted.status_code==200
    rows=client.get('/api/v1/workspaces/default/keys',headers=ah).json()
    om=next(k for k in rows if k['key_id']==old_id);nm=next(k for k in rows if k['key_id']==new_id)
    assert om['status']=='revoked' and nm['status']=='active' and nm['rotated_from_key_id']==old_id
    audit=client.get('/api/v1/workspaces/default/audit',headers=ah).json()
    assert any(x['action']=='api_key.rotated' and x['target_id']==new_id for x in audit)


def test_v07_usage_meter_counts_decision_once_under_idempotent_retry():
    reset()
    body={'workspace_id':'default','decision_type':'metered-refund','idempotency_key':'meter:one','agent':{'id':'meter-agent'}}
    a=client.post('/api/v1/decisions',json=body);b=client.post('/api/v1/decisions',json=body)
    assert a.status_code==200 and b.status_code==200 and b.json()['idempotent_replay'] is True
    usage=client.get('/api/v1/workspaces/default/usage').json()
    assert usage['billing_unit']=='consequential_decision' and usage['billable_decisions']==1 and usage['totals']['decision']==1


def test_v07_lifecycle_blocks_execution_before_required_approval_and_allows_idempotent_retry():
    reset()
    d=client.post('/api/v1/decisions',json={
        'workspace_id':'default','decision_type':'customer_refund','agent':{'id':'support-agent'},
        'authority':{'scope':['refund:create'],'limit_usd':1500},
        'model':{'provider':'local-test','name':'support-reasoner'},'context':{'prompt_version':'support-v1'},
        'proposed_action':{'tool':'stripe.refunds.create','amount':720},
    }).json();did=d['decision_id']
    assert client.post(f'/api/v1/decisions/{did}/events',json={'event_type':'model_completed','actor_type':'agent','actor_id':'support-agent','payload':{'response':'refund 720'}}).status_code==200
    pol=client.post('/api/v1/workspaces/default/policies/evaluate',json={'policy_id':'refund-policy','proposed_action':{'amount':720},'authority':{'limit_usd':1500}}).json()
    assert pol['decision']=='human_approval_required' and pol['policy_digest'] and pol['input_commitment']
    assert client.post(f'/api/v1/decisions/{did}/events',json={'event_type':'policy_evaluated','actor_type':'policy','actor_id':'refund-policy','payload':pol}).status_code==200
    premature=client.post(f'/api/v1/decisions/{did}/events',json={'event_type':'tool_executed','actor_type':'tool','actor_id':'stripe','payload':{'tool':'stripe.refunds.create'}})
    assert premature.status_code==409 and premature.json()['detail']['code']=='approval_required'
    approval={'event_type':'human_approved','actor_type':'human','actor_id':'risk@example.com','idempotency_key':'review:1','payload':{'reviewer':'risk@example.com','approved':True}}
    first=client.post(f'/api/v1/decisions/{did}/events',json=approval);retry=client.post(f'/api/v1/decisions/{did}/events',json=approval)
    assert first.status_code==200 and retry.status_code==200 and first.json()['event_id']==retry.json()['event_id']
    execution=client.post(f'/api/v1/decisions/{did}/events',json={'event_type':'tool_executed','actor_type':'tool','actor_id':'stripe','idempotency_key':'exec:1','payload':{'tool':'stripe.refunds.create','external_reference':'re_1'}})
    assert execution.status_code==200
    outcome=client.post(f'/api/v1/decisions/{did}/events',json={'event_type':'outcome_observed','actor_type':'system','actor_id':'observer','payload':{'status':'succeeded','external_reference':'re_1'}})
    assert outcome.status_code==200
    detail=client.get(f'/api/v1/decisions/{did}').json()
    assert detail['summary']['lifecycle']['state']=='evidence_complete' and detail['coverage']['complete'] is True


def test_v07_lifecycle_prevents_action_after_policy_block():
    reset()
    did=client.post('/api/v1/decisions',json={'workspace_id':'default','decision_type':'customer_refund','agent':{'id':'a'},'authority':{'limit_usd':1500},'proposed_action':{'tool':'stripe.refunds.create','amount':2400}}).json()['decision_id']
    pol=client.post('/api/v1/workspaces/default/policies/evaluate',json={'policy_id':'refund-policy','proposed_action':{'amount':2400},'authority':{'limit_usd':1500}}).json()
    assert pol['decision']=='blocked'
    assert client.post(f'/api/v1/decisions/{did}/events',json={'event_type':'policy_evaluated','actor_type':'policy','actor_id':'refund-policy','payload':pol}).status_code==200
    r=client.post(f'/api/v1/decisions/{did}/events',json={'event_type':'tool_executed','actor_type':'tool','actor_id':'stripe','payload':{'tool':'stripe.refunds.create'}})
    assert r.status_code==409 and r.json()['detail']['code']=='action_blocked'
    close=client.post(f'/api/v1/decisions/{did}/events',json={'event_type':'outcome_observed','actor_type':'system','actor_id':'policy-engine','payload':{'status':'blocked','reason':'no external action executed'}})
    assert close.status_code==200


def test_v07_policy_digest_and_input_commitment_are_deterministic_and_version_bound():
    reset()
    body={'policy_id':'refund-policy','proposed_action':{'amount':720},'authority':{'limit_usd':1500},'context':{'region':'US'}}
    a=client.post('/api/v1/workspaces/default/policies/evaluate',json=body).json();b=client.post('/api/v1/workspaces/default/policies/evaluate',json=body).json()
    assert a['policy_digest']==b['policy_digest'] and a['input_commitment']==b['input_commitment']
    created=client.post('/api/v1/workspaces/default/policies',json={'policy_id':'refund-policy','name':'Refund authority','version':'17.4','rule':{'type':'amount_threshold','field':'amount','auto_approve_max':500,'hard_limit':1500,'currency':'USD'},'active':True})
    assert created.status_code==200
    c=client.post('/api/v1/workspaces/default/policies/evaluate',json=body).json()
    assert c['version']=='17.4' and c['policy_digest']!=a['policy_digest'] and c['input_commitment']==a['input_commitment']


def test_v07_evidence_bundle_v2_contains_trust_lifecycle_policy_and_verifies(tmp_path):
    reset();did=client.post('/api/v1/demo/refund').json()['summary']['decision_id']
    p=tmp_path/'v07-bundle.zip';p.write_bytes(client.get(f'/api/v1/decisions/{did}/evidence').content)
    import zipfile,json
    with zipfile.ZipFile(p) as z:
        names=set(z.namelist());manifest=json.loads(z.read('manifest.json'))
        assert {'signer.json','verification.json','lifecycle.json','policy/policy.json','public-key.pem','events.jsonl','chain-witness.jsonl'} <= names
        assert manifest['bundle_schema']=='loopgrid/evidence-bundle/2' and manifest['version']=='3.0-draft'
        assert manifest['policy']['policy_digest'] and manifest['lifecycle']['state']=='evidence_complete'
    result=verify_bundle(str(p))
    assert result['valid'] is True and result['bundle_schema']=='loopgrid/evidence-bundle/2' and result['policy_digest']


def test_v07_request_body_limit_and_system_posture_are_exposed():
    # Content-Length is checked before parsing the body, providing an inexpensive abuse guard.
    too_big=client.get('/health',headers={'Content-Length':'3000000'})
    assert too_big.status_code==413
    info=client.get('/api/v1/system/info').json()
    assert info['database']['provider']=='sqlite' and info['database']['target_for_external_pilot']=='postgresql'
    assert info['lifecycle']['enforced'] is True


def test_v07_verifier_cli_ascii_safe_when_stdout_is_redirected(tmp_path):
    """Regression: verifier must not fail just because Windows pipe encoding is ASCII/legacy."""
    import subprocess, sys
    reset(); client.post('/api/v1/demo/workspace')
    did=client.get('/api/v1/decisions').json()[0]['decision_id']
    bundle=client.get(f'/api/v1/decisions/{did}/evidence').content
    p=tmp_path/'ascii-safe-evidence.zip'; p.write_bytes(bundle)
    key_id=verify_bundle(str(p))['key_identity']['computed_key_id']
    verifier=Path(__file__).resolve().parents[1]/'verifier'/'loopgrid_verify.py'
    env=os.environ.copy(); env['PYTHONIOENCODING']='ascii'
    proc=subprocess.run(
        [sys.executable,str(verifier),str(p),'--expected-key-id',key_id],
        capture_output=True,env=env,timeout=20
    )
    assert proc.returncode==0, proc.stderr.decode('ascii','replace')
    assert b'[OK] VERIFIED' in proc.stdout


def test_v071_api_key_issuance_respects_required_auth_boundary():
    """Anonymous callers must never mint service credentials when auth is required."""
    from app.config import settings
    reset()
    old_required = settings.require_user_auth
    try:
        object.__setattr__(settings, "require_user_auth", True)
        r = client.post(
            "/api/v1/workspaces/default/keys",
            json={"name": "anonymous-mint-attempt", "scopes": ["ingest"]},
        )
        assert r.status_code == 401
    finally:
        object.__setattr__(settings, "require_user_auth", old_required)


# ---------------------------------------------------------------------------
# v0.8 Design Partner Release safety gates
# ---------------------------------------------------------------------------

def test_v08_production_safety_guard_rejects_placeholders():
    from types import SimpleNamespace
    from app.config import production_safety_errors
    cfg=SimpleNamespace(
        environment='production',strict_production_safety=True,
        database_url='sqlite:///unsafe.db',require_user_auth=False,
        api_key='change-me-before-sharing',bootstrap_token='change-me',
        cors_origins=('*',),max_request_body_bytes=2_000_000,
    )
    errors=production_safety_errors(cfg)
    assert any('PostgreSQL' in e for e in errors)
    assert any('REQUIRE_USER_AUTH' in e for e in errors)
    assert any('PLATFORM_ADMIN_KEY' in e for e in errors)
    assert any('BOOTSTRAP_TOKEN' in e for e in errors)
    assert any('wildcard' in e for e in errors)


def test_v08_production_safety_guard_accepts_design_partner_config():
    from types import SimpleNamespace
    from app.config import production_safety_errors
    cfg=SimpleNamespace(
        environment='production',strict_production_safety=True,
        database_url='postgresql+psycopg://loopgrid:strong@db:5432/loopgrid',
        require_user_auth=True,api_key='lg_platform_'+'a'*32,
        bootstrap_token='lg_bootstrap_'+'b'*32,cors_origins=('https://console.example.com',),
        max_request_body_bytes=2_000_000,
    )
    assert production_safety_errors(cfg)==[]


def test_v08_system_info_exposes_deployment_security_posture():
    info=client.get('/api/v1/system/info').json()
    assert info['version'].startswith('0.8.1')
    assert 'deployment_security' in info
    assert info['deployment_security']['strict_production_safety'] is True
