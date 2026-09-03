class LoopGrid {
  constructor({baseUrl='http://localhost:8000', apiKey=null, workspaceId='default', bearerToken=null}={}) {
    this.baseUrl=baseUrl.replace(/\/$/,''); this.apiKey=apiKey; this.workspaceId=workspaceId; this.bearerToken=bearerToken;
  }
  async request(path,{method='GET',body=null,headers={}}={}) {
    const h={...headers};
    if(this.apiKey) h['X-LoopGrid-Key']=this.apiKey;
    if(this.bearerToken) h['Authorization']='Bearer '+String(this.bearerToken).replace(/^Bearer\s+/i,'');
    if(body!==null) h['Content-Type']='application/json';
    const r=await fetch(this.baseUrl+path,{method,headers:h,body:body===null?undefined:JSON.stringify(body)});
    if(!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    const ct=r.headers.get('content-type')||'';
    return ct.includes('json') ? r.json() : r.arrayBuffer();
  }
  recordDecision(data){return this.request('/api/v1/decisions',{method:'POST',body:{workspace_id:this.workspaceId,...data}})}
  getDecision(id){return this.request(`/api/v1/decisions/${id}`)}
  listDecisions(limit=100){return this.request(`/api/v1/decisions?workspace_id=${encodeURIComponent(this.workspaceId)}&limit=${limit}`)}
  addEvent(id,data){return this.request(`/api/v1/decisions/${id}/events`,{method:'POST',body:data})}
  modelCompleted(id,payload,actorId='agent',extra={}){return this.addEvent(id,{event_type:'model_completed',actor_type:'agent',actor_id:actorId,payload,...extra})}
  policyEvaluated(id,payload,actorId='policy',extra={}){return this.addEvent(id,{event_type:'policy_evaluated',actor_type:'policy',actor_id:actorId,payload,...extra})}
  humanApproved(id,reviewer,reason='',extra={}){return this.addEvent(id,{event_type:'human_approved',actor_type:'human',actor_id:reviewer,payload:{approved:true,reviewer,reason},...extra})}
  humanRejected(id,reviewer,reason='',extra={}){return this.addEvent(id,{event_type:'human_rejected',actor_type:'human',actor_id:reviewer,payload:{approved:false,reviewer,reason},...extra})}
  toolExecuted(id,payload,actorId='tool',extra={}){return this.addEvent(id,{event_type:'tool_executed',actor_type:'tool',actor_id:actorId,payload,...extra})}
  outcomeObserved(id,payload,actorId='outcome-observer',extra={}){return this.addEvent(id,{event_type:'outcome_observed',actor_type:'system',actor_id:actorId,payload,...extra})}
  policies(){return this.request(`/api/v1/workspaces/${this.workspaceId}/policies`)}
  evaluatePolicy(policyId,proposedAction,authority={},context={}){return this.request(`/api/v1/workspaces/${this.workspaceId}/policies/evaluate`,{method:'POST',body:{policy_id:policyId,proposed_action:proposedAction,authority,context}})}
  reviews(){return this.request(`/api/v1/reviews?workspace_id=${encodeURIComponent(this.workspaceId)}`)}
  review(id,action,reviewer,reason=''){return this.request(`/api/v1/decisions/${id}/review`,{method:'POST',body:{action,reviewer,reason}})}
  verifyWorkspace(){return this.request(`/api/v1/integrity/verify?workspace_id=${encodeURIComponent(this.workspaceId)}`)}
  checkpoint(){return this.request(`/api/v1/workspaces/${this.workspaceId}/checkpoint`,{method:'POST',body:{}})}
  exportEvidence(id,includePayloads=true){return this.request(`/api/v1/decisions/${id}/evidence?include_payloads=${includePayloads?'true':'false'}`)}
  systemInfo(){return this.request('/api/v1/system/info')}
  readiness(){return this.request('/ready')}
  pilotReadiness(){return this.request('/api/v1/pilot/readiness')}
  replay(id,data){return this.request(`/api/v1/decisions/${id}/replay`,{method:'POST',body:data})}
  ingestOTel(spans){return this.request('/api/v1/ingest/otel',{method:'POST',body:{workspace_id:this.workspaceId,spans}})}
  ingestMCP(request,response=null,extra={}){return this.request('/api/v1/ingest/mcp',{method:'POST',body:{workspace_id:this.workspaceId,request,response,...extra}})}
  payloadStatus(id){return this.request(`/api/v1/decisions/${id}/payload-status`)}
  erasePayload(id,reason='customer_request'){return this.request(`/api/v1/decisions/${id}/payload/erase`,{method:'POST',body:{reason}})}
  runRetention(){return this.request(`/api/v1/workspaces/${this.workspaceId}/retention/run`,{method:'POST',body:{}})}
  // backward-compatibility aliases
  decision(id){return this.getDecision(id)}
  decisions(limit=100){return this.listDecisions(limit)}
  verify(){return this.verifyWorkspace()}
  evidence(id,includePayloads=true){return this.exportEvidence(id,includePayloads)}
}
module.exports={LoopGrid};
