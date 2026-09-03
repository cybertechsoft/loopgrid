let currentDecision = null;
let currentDecisionData = null;
let decisionsCache = [];
let quickFilter = 'all';

const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const titleize = (s) => String(s || '').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
const money = (n) => Number.isFinite(Number(n)) ? `$${Number(n).toLocaleString()}` : '—';
const shortId = (id) => id ? `${id.slice(0,8)}…${id.slice(-5)}` : '—';

function toast(msg, ms=2600){
  const t=$('toast');
  if(!t){ console.warn('[LoopGrid UI]', msg); return; }
  t.textContent=msg; t.classList.remove('hidden');
  clearTimeout(window.__toastTimer); window.__toastTimer=setTimeout(()=>t.classList.add('hidden'),ms);
}

function showBootError(err){
  console.error('[LoopGrid UI] startup error', err);
  let box=document.getElementById('uiBootError');
  if(!box){
    box=document.createElement('div');
    box.id='uiBootError';
    box.style.cssText='position:fixed;left:18px;right:18px;bottom:18px;z-index:9999;background:#fff4f4;border:1px solid #c84d55;padding:14px 16px;font:13px/1.45 ui-monospace,monospace;color:#7a2228;box-shadow:0 10px 35px rgba(0,0,0,.12)';
    document.body.appendChild(box);
  }
  box.innerHTML='<strong>LoopGrid UI could not start.</strong><br>'+esc(err?.message||err)+'<br><small>Hard refresh once (Ctrl+Shift+R). If this remains, open DevTools → Console and copy the first red error.</small>';
}


async function api(url, options={}){
  const r=await fetch(url,{cache:'no-store',headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
  if(!r.ok) throw new Error(await r.text());
  if(r.status===204) return null;
  return r.json();
}

function policyClass(decision){
  if(decision==='blocked'||decision==='block') return 'blocked';
  if(decision==='human_approval_required') return 'warn';
  return 'success';
}

function outcomeClass(status){
  if(status==='blocked'||status==='failed') return 'blocked';
  if(status==='pending'||!status) return 'warn';
  return 'success';
}

function setIntegrity(dash){
  const hasEvents = dash.events > 0;
  const valid = !!dash.integrity_valid;
  const shield=$('integrityShield'), top=$('topIntegrity');
  if(!hasEvents){
    shield.className='integrity-shield ready'; $('integrityIcon').textContent='✓';
    $('integrityLabel').textContent='READY'; $('integrityMeta').textContent='No evidence recorded yet.';
    top.className='top-integrity ready'; top.innerHTML='<span class="status-dot"></span><span>Evidence ready</span>';
  } else if(valid){
    shield.className='integrity-shield verified'; $('integrityIcon').textContent='✓';
    $('integrityLabel').textContent='VERIFIED'; $('integrityMeta').textContent=`${dash.events.toLocaleString()} signed events · chain intact`;
    top.className='top-integrity verified'; top.innerHTML='<span class="status-dot ok"></span><span>Ledger verified</span>';
  } else {
    shield.className='integrity-shield invalid'; $('integrityIcon').textContent='!';
    $('integrityLabel').textContent='INTEGRITY ALERT'; $('integrityMeta').textContent='One or more signed records failed verification.';
    top.className='top-integrity invalid'; top.innerHTML='<span class="status-dot"></span><span>Integrity alert</span>';
  }
  $('keyShort').textContent=dash.key_id ? dash.key_id.replace('ed25519:','').slice(0,10) : '—';
}

function renderCoverage(coverage, listEl, scoreEl, stateEl=null){
  if(!coverage){ return; }
  scoreEl.textContent=coverage.complete ? '100%' : `${coverage.passed}/${coverage.total}`;
  if(stateEl) stateEl.textContent=coverage.label || (coverage.complete?'Evidence complete':'Evidence in progress');
  listEl.innerHTML=coverage.checks.map(c=>{
    const st=c.status || (c.present?'present':'missing');
    const icon=st==='present'?'✓':st==='pending'?'…':st==='not_applicable'?'—':'!';
    return `<div class="coverage-item ${esc(st)}"><span>${icon}</span>${esc(c.label)}${st==='pending'?'<small>pending</small>':st==='not_applicable'?'<small>n/a</small>':''}</div>`;
  }).join('');
}

function rowHtml(d, compact=false){
  const action=d.proposed_action||{}, policy=d.policy||{}, outcome=d.outcome||{}, agent=d.agent||{};
  const pDecision=policy.decision||'not evaluated';
  const status=outcome.status||'pending';
  const coverage=d.coverage||{}; const evidence=coverage.score ?? 0;
  const evidenceBadge=coverage.complete?'✓ 100%':coverage.state==='integrity_alert'?'! alert':(coverage.state||'').startsWith('awaiting_')?'… in progress':`${evidence}%`;
  if(compact){
    return `<tr data-id="${esc(d.decision_id)}">
      <td><span class="decision-id">${esc(shortId(d.decision_id))}</span></td>
      <td><div class="agent-cell"><span class="mini-avatar">${esc((agent.id||'A').slice(0,1).toUpperCase())}</span><strong>${esc(agent.id||'—')}</strong></div></td>
      <td><strong>${esc(action.tool||'—')}</strong>${action.amount!=null?`<br><span>${money(action.amount)}</span>`:''}</td>
      <td><span class="pill-status ${policyClass(pDecision)}"><span class="status-dot ${pDecision==='auto_allowed'?'ok':''}"></span>${esc(titleize(pDecision))}</span></td>
      <td><span class="pill-status ${outcomeClass(status)}"><span class="status-dot ${status==='succeeded'?'ok':''}"></span>${esc(titleize(status))}</span></td>
      <td><span class="pill-status proof">${esc(evidenceBadge)}</span></td>
      <td class="row-chevron">›</td>
    </tr>`;
  }
  return `<tr data-id="${esc(d.decision_id)}">
    <td><span class="decision-id">${esc(shortId(d.decision_id))}</span></td>
    <td>${esc(titleize(d.decision_type||'—'))}</td>
    <td><div class="agent-cell"><span class="mini-avatar">${esc((agent.id||'A').slice(0,1).toUpperCase())}</span><strong>${esc(agent.id||'—')}</strong></div></td>
    <td><strong>${esc(action.tool||'—')}</strong>${action.amount!=null?`<br><span>${money(action.amount)}</span>`:''}</td>
    <td><span class="pill-status ${policyClass(pDecision)}">${esc(titleize(pDecision))}</span></td>
    <td><span class="pill-status ${outcomeClass(status)}">${esc(titleize(status))}</span></td>
    <td><span class="pill-status proof">✓ signed</span></td>
  </tr>`;
}

function filterDecisions(decisions, q, useQuick=true){
  q=(q||'').trim().toLowerCase();
  return decisions.filter(d=>{
    if(q && !JSON.stringify(d).toLowerCase().includes(q)) return false;
    if(!useQuick || quickFilter==='all') return true;
    const pd=(d.policy||{}).decision;
    if(quickFilter==='review') return pd==='human_approval_required';
    if(quickFilter==='blocked') return pd==='blocked'||pd==='block';
    return true;
  });
}

function wireRows(container){
  container.querySelectorAll('tr[data-id]').forEach(tr=>tr.onclick=()=>openDecision(tr.dataset.id));
}

function renderDecisionTables(){
  const q1=$('filter').value, q2=$('filter2').value;
  const list1=filterDecisions(decisionsCache,q1,true);
  const list2=filterDecisions(decisionsCache,q2,false);
  $('decisionRows').innerHTML=list1.map(d=>rowHtml(d,true)).join('');
  $('decisionRows2').innerHTML=list2.map(d=>rowHtml(d,false)).join('');
  wireRows($('decisionRows')); wireRows($('decisionRows2'));
  $('emptyState').classList.toggle('hidden',decisionsCache.length>0);
  $('emptyState2').classList.toggle('hidden',decisionsCache.length>0);
  $('navDecisionCount').textContent=decisionsCache.length;
}

async function refresh(){
  const [dash, decisions]=await Promise.all([api('/api/v1/dashboard'),api('/api/v1/decisions')]);
  decisionsCache=decisions;
  $('mDecisions').textContent=dash.decisions.toLocaleString();
  $('mEvents').textContent=dash.events.toLocaleString();
  $('mApprovals').textContent=(dash.completed_reviews ?? (dash.human_approvals + (dash.human_rejections||0))).toLocaleString();
  if($('mReviewSub')) $('mReviewSub').textContent=`${dash.completed_reviews||0} completed · ${dash.pending_reviews||0} awaiting review`;
  if($('navReviewCount')) $('navReviewCount').textContent=(dash.pending_reviews||0).toLocaleString();
  $('mOutcomes').textContent=dash.outcome_verified.toLocaleString();
  $('mDecisionSub').textContent=dash.decisions ? `${dash.auto_allowed} auto-allowed · ${dash.policy_blocks} policy-blocked` : 'No recorded decisions yet';
  setIntegrity(dash);
  renderDecisionTables();
  if(decisions.length){
    $('coverageEmpty').classList.add('hidden'); $('coverageList').classList.remove('hidden');
    renderCoverage(decisions[0].coverage,$('coverageList'),$('coverageBadge'),$('coverageStateText'));
  } else {
    $('coverageEmpty').classList.remove('hidden'); $('coverageList').classList.add('hidden'); $('coverageBadge').textContent='—'; if($('coverageStateText')) $('coverageStateText').textContent='No record selected.';
  }
}

function eventSummary(e){
  const p=e.payload||{};
  switch(e.event_type){
    case 'decision_created': return `${titleize(p.decision_type)} proposed by ${(p.agent||{}).id||'agent'} for ${money((p.proposed_action||{}).amount)}.`;
    case 'model_completed': return p.response||'Model completed.';
    case 'policy_evaluated': return `${titleize(p.decision)} · policy ${p.version||'—'} · threshold ${money(p.human_approval_threshold)}.`;
    case 'human_approved': return `${p.reviewer||e.actor.id} approved the proposed action.`;
    case 'human_rejected': return `${p.reviewer||e.actor.id} rejected the proposed action.`;
    case 'tool_executed': return `${p.tool||'Tool'} executed${p.external_reference?` · ${p.external_reference}`:''}.`;
    case 'outcome_observed': return `${titleize(p.status)} verified against ${p.verified_against||'external system'}.`;
    case 'replay_executed': return 'Counterfactual analysis appended without changing the original production events.';
    case 'mcp_tool_requested': return `MCP tool request captured · ${p.tool||'tool'}.`;
    case 'mcp_tool_result': return 'MCP tool result captured and bound to this decision.';
    case 'tool_requested': return `Tool request captured · ${p.tool||'tool'}.`;
    case 'tool_result': return 'Tool result captured from the agent runtime.';
    case 'incident_flagged': return p.message||'Runtime incident captured.';
    case 'payload_erased': return 'Encrypted disclosure payloads erased while cryptographic commitments remain in the signed ledger.';
    default: return titleize(e.event_type);
  }
}

function contextValue(v){
  if(v==null) return '—';
  if(typeof v==='string'||typeof v==='number'||typeof v==='boolean') return String(v);
  if(Array.isArray(v)) return v.join(', ')||'—';
  return Object.entries(v).map(([k,val])=>`${titleize(k)}: ${typeof val==='object'?JSON.stringify(val):val}`).join(' · ')||'—';
}

function renderDecisionDrawer(d){
  currentDecisionData=d;
  const s=d.summary, v=d.verification, c=d.coverage;
  const action=s.proposed_action||{}, policy=s.policy||{}, outcome=s.outcome||{}, agent=s.agent||{}, authority=s.authority||{}, model=s.model||{}, context=s.context||{};
  $('dTitle').textContent=s.decision_id;
  $('dSubtitle').textContent=`${titleize(s.decision_type)} · ${new Date(s.created_at).toLocaleString()}`;
  $('dVerify').className='verification-banner '+(v.valid?'':'bad');
  $('dVerify').innerHTML=`<div class="verify-main"><div class="verify-icon">${v.valid?'✓':'!'}</div><div class="verify-copy"><strong>${v.valid?'Evidence verified':'Integrity verification failed'}</strong><span>${v.checked_events} decision events · ${esc(v.algorithm)}</span></div></div><div class="verify-key">${esc(v.key_id)}</div>`;
  $('reportLink').href=`/api/v1/decisions/${s.decision_id}/report`;
  $('downloadLink').href=`/api/v1/decisions/${s.decision_id}/evidence`;

  const approval=s.approval||{};
  const approvalLabel=policy.decision==='human_approval_required' ? (s.approval_event==='human_approved'?'Approved':'Review required') : policy.decision==='blocked'?'Not executed':'Not required';
  $('summaryGrid').innerHTML=`
    <div class="summary-card"><div class="label">Proposed action</div><strong>${esc(action.tool||'—')}</strong><small>${action.amount!=null?money(action.amount):'No monetary value'} ${esc(action.currency||'')}</small></div>
    <div class="summary-card"><div class="label">Observed outcome</div><strong>${esc(titleize(outcome.status||'pending'))}</strong><small>${esc(outcome.verified_against||'No external outcome observed')}</small></div>
    <div class="summary-card"><div class="label">Policy</div><strong>${esc((policy.policy_id||'—')+' · v'+(policy.version||'—'))}</strong><small>${esc(titleize(policy.decision||'not evaluated'))}</small></div>
    <div class="summary-card"><div class="label">Human oversight</div><strong>${esc(approvalLabel)}</strong><small>${esc(approval.reviewer||policy.reason||'No reviewer required')}</small></div>
    <div class="summary-card"><div class="label">Agent</div><strong>${esc(agent.id||'—')}</strong><small>v${esc(agent.version||'—')} · ${esc(agent.deployment_sha||'no deployment hash')}</small></div>
    <div class="summary-card"><div class="label">Model</div><strong>${esc(model.name||'—')}</strong><small>${esc(model.provider||'—')} · temperature ${esc(model.temperature??'—')}</small></div>`;

  renderCoverage(c,$('drawerCoverage'),$('drawerCoverageScore'),$('drawerCoverageState'));
  $('contextCards').innerHTML=`
    <div class="context-card"><span>Acting for</span><strong>${esc(authority.acting_for||'—')}</strong></div>
    <div class="context-card"><span>Authority scope</span><strong>${esc(contextValue(authority.scope))}</strong></div>
    <div class="context-card"><span>Prompt version</span><strong>${esc(context.prompt_version||'—')}</strong></div>
    <div class="context-card"><span>Retrieval provenance</span><strong>${esc(contextValue(context.retrieval_refs))}</strong></div>`;
  $('rawSummary').textContent=JSON.stringify(s,null,2);

  $('timelineCount').textContent=`${d.events.length} events`;
  $('timeline').innerHTML=d.events.map(e=>`<div class="event event-${esc(e.event_type)}">
    <div class="event-head"><div class="event-title"><strong>${esc(titleize(e.event_type))}</strong><span>${esc(e.actor.type)} · ${esc(e.actor.id)}</span></div><div class="event-time">${esc(new Date(e.occurred_at).toLocaleTimeString())}</div></div>
    <div class="event-summary">${esc(eventSummary(e))}</div>
    <details><summary>View signed payload</summary><pre>${esc(JSON.stringify(e.payload,null,2))}</pre></details>
  </div>`).join('');

  $('proofSeal').textContent=v.valid?'✓':'!';
  $('proofStatus').textContent=v.valid?'Evidence verified':'Evidence verification failed';
  $('proofText').textContent=v.valid?`Every decision event passed content-hash, workspace-chain and ${v.signature_algorithm||'digital'} signature verification.`:'At least one evidence integrity check failed.';
  const first=d.events[0]?.proof||{}, last=d.events[d.events.length-1]?.proof||{};
  $('proofDetails').innerHTML=`
    <div class="proof-detail"><span>Signing key</span><code>${esc(v.key_id)}</code></div>
    <div class="proof-detail"><span>Algorithm</span><code>${esc(v.algorithm)}</code></div>
    <div class="proof-detail"><span>First content hash</span><code>${esc(first.content_hash||'—')}</code></div>
    <div class="proof-detail"><span>Latest chain hash</span><code>${esc(last.chain_hash||'—')}</code></div>`;
  $('tamperResult').classList.add('hidden');
  $('replayComparison').classList.add('hidden'); $('replayPlaceholder').classList.remove('hidden');
  $('threshold').value=1000;
}

async function openDecision(id, tab='summary'){
  const d=await api(`/api/v1/decisions/${id}`); currentDecision=id; renderDecisionDrawer(d); switchTab(tab); $('drawer').classList.remove('hidden');
}

function switchTab(tab){
  document.querySelectorAll('#decisionTabs button').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.toggle('active',p.id===`tab-${tab}`));
}

async function loadWorkspace(){
  const buttons=[$('loadWorkspace'),$('emptyLoadDemo'),$('emptyLoadDemo2')]; buttons.forEach(b=>b&&(b.disabled=true));
  try{toast('Building signed demo workspace…');const r=await api('/api/v1/demo/workspace',{method:'POST',body:'{}'});await refresh();toast(`${r.count} decision scenarios created and signed`);if(r.created?.[1]) await openDecision(r.created[1]);}
  catch(e){toast(e.message,4200)}finally{buttons.forEach(b=>b&&(b.disabled=false));}
}

async function runOneDemo(){
  $('runOneDemo').disabled=true;
  try{toast('Creating $720 human-approval decision…');const r=await api('/api/v1/demo/refund',{method:'POST',body:'{}'});await refresh();await openDecision(r.summary.decision_id);toast('Signed decision evidence created');}
  catch(e){toast(e.message,4200)}finally{$('runOneDemo').disabled=false;}
}

async function resetDemo(){
  if(!confirm('Reset the local demo ledger? This deletes only your local demo data.')) return;
  try{await api('/api/v1/demo/reset',{method:'DELETE'});currentDecision=null;decisionsCache=[];await refresh();toast('Local demo workspace reset');}
  catch(e){toast(e.message,4200)}
}

async function verifyLedger(){
  try{const v=await api('/api/v1/integrity/verify');toast(v.total_ledger_events===0?'Ledger ready — no evidence recorded yet':v.valid?`Verified ${v.total_ledger_events} signed events`:`Integrity alert · ${v.failures.length} failures`);await refresh();}
  catch(e){toast(e.message,4200)}
}

async function runReplay(){
  if(!currentDecision) return;
  const threshold=parseFloat($('threshold').value);
  if(!Number.isFinite(threshold)||threshold<0){toast('Enter a valid approval threshold');return;}
  $('replayBtn').disabled=true;$('replayBtn').textContent='Running…';
  try{
    const r=await api(`/api/v1/decisions/${currentDecision}/replay`,{method:'POST',body:JSON.stringify({mode:'policy',policy_threshold:threshold})});
    const o=r.original||{}, c=r.counterfactual||{};
    $('replayPlaceholder').classList.add('hidden'); $('replayComparison').classList.remove('hidden');
    $('replayComparison').innerHTML=`<div class="compare-grid">
      <div class="compare-card"><div class="compare-label">Production policy</div><div class="compare-decision">${esc(titleize(o.decision))}</div><div class="compare-detail">Threshold ${money(o.threshold)} · amount ${money(o.amount)} · v${esc(o.policy_version||'—')}</div></div>
      <div class="compare-arrow">→</div>
      <div class="compare-card ${r.changed?'changed':''}"><div class="compare-label">Counterfactual</div><div class="compare-decision">${esc(titleize(c.decision))}</div><div class="compare-detail">Threshold ${money(c.threshold)} · same historical amount ${money(c.amount)}</div></div>
    </div><div class="${r.changed?'changed-banner':'unchanged-banner'}"><strong>${r.changed?'Decision changed':'Decision unchanged'}.</strong> ${esc(r.explanation||'')}</div>`;
    await refresh();
    currentDecisionData=await api(`/api/v1/decisions/${currentDecision}`);
    toast(r.changed?'Counterfactual changed the policy outcome':'Counterfactual produced the same outcome');
  }catch(e){toast(e.message,4200)}finally{$('replayBtn').disabled=false;$('replayBtn').textContent='Run replay';}
}

async function runTamper(){
  if(!currentDecision) return;
  $('tamperBtn').disabled=true;$('tamperBtn').textContent='Testing…';
  try{
    const r=await api(`/api/v1/decisions/${currentDecision}/tamper-test`,{method:'POST',body:'{}'});
    const t=r.simulated_tamper;
    $('tamperResult').classList.remove('hidden');
    $('tamperResult').innerHTML=`<div class="tamper-title"><span>✕</span><span>${t.detected?'TAMPERING DETECTED':'Unexpected verification result'}</span></div><p>Modified copy: ${esc(titleize(t.event_type))} · ${esc(shortId(t.event_id))}. Production record unchanged: ${r.production_record_unchanged?'yes':'no'}.</p><div class="reason-chips">${t.reasons.map(x=>`<span>${esc(x)}</span>`).join('')}</div>`;
    toast(t.detected?'Tamper test passed — modified evidence was rejected':'Tamper test did not detect modification',3500);
  }catch(e){toast(e.message,4200)}finally{$('tamperBtn').disabled=false;$('tamperBtn').textContent='Run tamper test';}
}


async function loadReviews(){
  try{
    const items=await api('/api/v1/reviews?workspace_id=default');
    $('reviewQueueCount').textContent=items.length; $('navReviewCount').textContent=items.length;
    $('reviewEmpty').classList.toggle('hidden',items.length>0);
    $('reviewQueue').innerHTML=items.map(r=>{const a=r.action||{},p=r.policy||{},ag=r.agent||{};return `<article class="review-row"><div class="review-main"><span class="decision-id">${esc(shortId(r.decision_id))}</span><h3>${esc(titleize(r.decision_type))}</h3><p>${esc(ag.id||'agent')} proposes <b>${esc(a.tool||'action')}</b>${a.amount!=null?` for ${money(a.amount)}`:''}.</p></div><div class="review-policy"><span>Policy</span><strong>${esc(p.policy_id||'—')} · v${esc(p.version||'—')}</strong><small>${esc(titleize(p.reason||p.decision||''))}</small></div><div class="review-actions"><button class="button outline review-reject" data-id="${esc(r.decision_id)}">Reject</button><button class="button ink review-approve" data-id="${esc(r.decision_id)}">Approve</button></div></article>`}).join('');
    document.querySelectorAll('.review-approve').forEach(b=>b.onclick=()=>submitReview(b.dataset.id,'approve')); document.querySelectorAll('.review-reject').forEach(b=>b.onclick=()=>submitReview(b.dataset.id,'reject'));
  }catch(e){toast(e.message,4200)}
}
async function createPendingReview(){try{toast('Creating policy-gated decision…');await api('/api/v1/demo/pending-review',{method:'POST',body:'{}'});await refresh();await loadReviews();toast('Decision added to human review queue')}catch(e){toast(e.message,4200)}}
async function submitReview(id,action){const reviewer='risk@acme.example';const reason=action==='approve'?'Reviewed against duplicate-charge evidence':'Rejected during pilot review';try{await api(`/api/v1/decisions/${id}/review`,{method:'POST',body:JSON.stringify({action,reviewer,reason})});await refresh();await loadReviews();toast(`Decision ${action==='approve'?'approved':'rejected'} and signed`);await openDecision(id,'timeline')}catch(e){toast(e.message,4200)}}
async function loadPolicies(){try{const items=await api('/api/v1/workspaces/default/policies');$('policyList').innerHTML=items.length?items.map(p=>{const r=p.rule||{};return `<div class="policy-row ${p.active?'active':''}"><div><span class="policy-state">${p.active?'ACTIVE':'HISTORY'}</span><h3>${esc(p.name)}</h3><p>${esc(p.policy_id)} · version ${esc(p.version)}</p></div><div class="policy-thresholds"><span>Auto approve <b>${money(r.auto_approve_max)}</b></span><span>Hard limit <b>${money(r.hard_limit)}</b></span></div></div>`}).join(''):'<div class="coverage-empty">No policies in this workspace.</div>'}catch(e){toast(e.message,4200)}}
async function createPolicyVersion(){const version=$('policyVersion').value.trim(),auto=Number($('policyAuto').value),hard=Number($('policyHard').value);if(!version||!Number.isFinite(auto)||!Number.isFinite(hard)||hard<=auto){toast('Enter a version and a hard limit above the auto-approval threshold');return}try{const r=await api('/api/v1/workspaces/default/policies',{method:'POST',body:JSON.stringify({policy_id:'refund-policy',name:'Refund authority',version,active:true,rule:{type:'amount_threshold',field:'amount',auto_approve_max:auto,hard_limit:hard,currency:'USD'}})});$('policyResult').classList.remove('hidden');$('policyResult').textContent=`Active policy: ${r.policy_id} v${r.version}\nAuto approve: ${money(r.rule.auto_approve_max)}\nHard limit: ${money(r.rule.hard_limit)}\n\nHistorical signed decisions are unchanged.`;await loadPolicies();toast(`Policy v${r.version} activated`)}catch(e){toast(e.message,4200)}}

async function loadTrust(){
  try{
    const info=await api('/api/v1/system/info');
    const sg=info.signer||{},ts=info.timestamping||{},vault=info.payload_vault||{},mcp=info.mcp_proxy||{};
    if($('envSigner')) $('envSigner').textContent=sg.algorithm||sg.provider||'—';
    if($('envTsa')) $('envTsa').textContent=ts.tsa_url_configured?'Configured':'Not set';
    if($('envTsaSignal')) $('envTsaSignal').className='signal '+(ts.tsa_url_configured?'ok':'warn');
    if($('sidebarVersion')) $('sidebarVersion').textContent='v'+String(info.version||'0.8.0').split('-')[0];
    if($('trustSigner')) $('trustSigner').textContent=sg.provider==='aws_kms'?'AWS KMS signing boundary':'Local Ed25519 signer';
    if($('trustSignerNote')) $('trustSignerNote').textContent=sg.hardware_backed?'Asymmetric signing is executed by the configured AWS KMS key.':'Zero-setup local signer for design-partner evaluation. Use KMS for a hardware-backed production boundary.';
    if($('trustAlgorithm')) $('trustAlgorithm').textContent=sg.algorithm||'—';
    if($('trustKey')) $('trustKey').textContent=sg.key_id||'—';
    if($('trustHardware')) $('trustHardware').textContent=sg.hardware_backed?'Yes':'No';
    if($('trustVaultSource')) $('trustVaultSource').textContent=vault.key_source||'—';
    if($('trustTsa')) $('trustTsa').textContent=ts.tsa_url_configured?'RFC 3161 configured':'No external TSA';
    if($('trustTsaNote')) $('trustTsaNote').textContent=ts.tsa_url_configured?'Checkpoints request an RFC 3161 response and bind it to the current chain head.':'Signed checkpoints are local until LOOPGRID_TSA_URL is configured.';
    if($('trustProfile')) $('trustProfile').textContent=info.evidence_profile||'—';
    if($('trustVersion')) $('trustVersion').textContent=info.version||'—';
    if($('trustMcp')) $('trustMcp').textContent=mcp.enabled?`Configured aliases: ${(mcp.configured_aliases||[]).join(', ')}`:'No MCP proxy upstreams configured. LoopGrid intentionally rejects arbitrary target URLs.';
    if($('systemInfoRaw')) $('systemInfoRaw').textContent=JSON.stringify(info,null,2);
    try{
      const readiness=await api('/api/v1/pilot/readiness');
      if($('pilotReadinessTitle')) $('pilotReadinessTitle').textContent=readiness.overall;
      if($('pilotReadinessText')) $('pilotReadinessText').textContent=readiness.production_ready?'Production prerequisites are configured.':'Core pilot path is ready; warnings below identify production-boundary gaps.';
      if($('pilotReadinessChecks')) $('pilotReadinessChecks').innerHTML=readiness.checks.map(c=>`<div class="readiness-item ${esc(c.status)}"><span>${c.status==='pass'?'✓':c.status==='warning'?'!':'·'}</span><div><b>${esc(c.message)}</b>${c.detail?`<small>${esc(c.detail)}</small>`:''}</div></div>`).join('');
    }catch(e){if($('pilotReadinessTitle')) $('pilotReadinessTitle').textContent='Readiness unavailable';}
    return info;
  }catch(e){toast(e.message,4200);return null}
}
async function runRetention(){
  try{const r=await api('/api/v1/workspaces/default/retention/run',{method:'POST',body:'{}'});const out=$('retentionResult');if(out){out.classList.remove('hidden');out.textContent=JSON.stringify(r,null,2)};toast(`${r.erased_payloads} expired disclosure payloads erased; ledger integrity ${r.ledger_integrity_valid?'valid':'invalid'}`);await refresh()}catch(e){toast(e.message,4200)}
}
async function createTrustCheckpoint(){
  try{const r=await api('/api/v1/workspaces/default/checkpoint',{method:'POST',body:'{}'});toast(r.status==='empty'?'No chain head to checkpoint yet':(r.external_timestamp?'Checkpoint + RFC3161 timestamp created':'Signed checkpoint created'));await loadTrust()}catch(e){toast(e.message,4200)}
}

// Front-end bootstrap. All bindings are installed only after the DOM is ready.
function bindClick(id, handler){
  const el=$(id);
  if(!el){ console.warn(`[LoopGrid UI] optional control #${id} not found`); return; }
  el.addEventListener('click', handler);
}
function bindInput(id, handler){
  const el=$(id);
  if(!el){ console.warn(`[LoopGrid UI] optional input #${id} not found`); return; }
  el.addEventListener('input', handler);
}

async function bootLoopGridUI(){
  if(window.__loopgridBooted) return;
  try{
    // Navigation
    for(const btn of document.querySelectorAll('.nav-item')){
      btn.addEventListener('click', async()=>{
        document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x===btn));
        document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
        const target=$(`view-${btn.dataset.view}`);
        if(!target) throw new Error(`Missing view: ${btn.dataset.view}`);
        target.classList.add('active');
        if(btn.dataset.view==='reviews') await loadReviews();
        if(btn.dataset.view==='policies') await loadPolicies();
        if(btn.dataset.view==='trust') await loadTrust();
      });
    }

    for(const b of document.querySelectorAll('#quickFilters button')){
      b.addEventListener('click',()=>{quickFilter=b.dataset.filter;document.querySelectorAll('#quickFilters button').forEach(x=>x.classList.toggle('active',x===b));renderDecisionTables();});
    }
    for(const b of document.querySelectorAll('#decisionTabs button')) b.addEventListener('click',()=>switchTab(b.dataset.tab));
    for(const x of document.querySelectorAll('[data-close]')) x.addEventListener('click',()=>{const d=$('drawer'); if(d)d.classList.add('hidden');});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){const d=$('drawer');if(d)d.classList.add('hidden');}});

    bindInput('filter',renderDecisionTables); bindInput('filter2',renderDecisionTables);
    bindClick('toggleRaw',()=>{const raw=$('rawSummary'); if(!raw)return; raw.classList.toggle('hidden'); const t=$('toggleRaw'); if(t)t.textContent=raw.classList.contains('hidden')?'View raw JSON':'Hide raw JSON';});
    bindClick('loadWorkspace',loadWorkspace); bindClick('emptyLoadDemo',loadWorkspace); bindClick('emptyLoadDemo2',loadWorkspace);
    bindClick('runOneDemo',runOneDemo); bindClick('resetDemo',resetDemo);
    bindClick('verifyLedger',verifyLedger); bindClick('verifyLedgerInline',verifyLedger);
    bindClick('replayBtn',runReplay); bindClick('tamperBtn',runTamper);
    bindClick('evidenceTamperCTA',()=>{if(decisionsCache.length)openDecision(decisionsCache[0].decision_id,'proof');else loadWorkspace();});
    bindClick('createReviewDemo',createPendingReview); bindClick('createReviewDemo2',createPendingReview);
    bindClick('refreshPolicies',loadPolicies); bindClick('createPolicyVersion',createPolicyVersion);
    bindClick('runRetentionBtn',runRetention); bindClick('trustCheckpointBtn',createTrustCheckpoint);

    bindClick('checkpointBtn',async()=>{
      try{
        const r=await api('/api/v1/workspaces/default/checkpoint',{method:'POST',body:'{}'});
        const out=$('checkpointResult'); if(out){out.classList.remove('hidden');out.textContent=JSON.stringify(r,null,2);}
        toast(r.status==='empty'?'No chain head to checkpoint yet':'Workspace chain head attested');
      }catch(e){toast(e.message,4200)}
    });
    bindClick('generateKeyBtn',async()=>{
      try{
        const r=await api('/api/v1/workspaces/default/keys',{method:'POST',body:JSON.stringify({name:'Local pilot ingestion',scopes:['ingest','read']})});
        const out=$('generatedKey'); if(out){out.classList.remove('hidden');out.textContent=`${r.api_key}\n\n${r.warning}`;}
        toast('Workspace API key generated');
      }catch(e){toast(e.message,4200)}
    });

    window.__loopgridBooted=true;
    window.LoopGridUI={version:'0.8.0',loadWorkspace,refresh,verifyLedger,loadTrust};
    await Promise.all([refresh(),loadTrust()]);
    console.info('[LoopGrid UI] v0.8 Design Partner Release ready');
  }catch(err){
    window.__loopgridBooted=false;
    showBootError(err);
  }
}

window.addEventListener('error',e=>{ if(!window.__loopgridBooted) showBootError(e.error||new Error(e.message)); });
window.addEventListener('unhandledrejection',e=>{ if(!window.__loopgridBooted) showBootError(e.reason instanceof Error?e.reason:new Error(String(e.reason))); });
window.bootLoopGridUI=bootLoopGridUI;
window.__loopgridRuntimeLoaded=true;
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',bootLoopGridUI,{once:true});
else bootLoopGridUI();
// A second idempotent attempt makes startup deterministic across embedded/local browsers.
setTimeout(()=>{ if(!window.__loopgridBooted) bootLoopGridUI(); },250);
