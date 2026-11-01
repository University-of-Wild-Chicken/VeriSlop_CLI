"use strict";

const ICONS = {
  layers:'<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>',
  shield:'<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z"/><path d="m8 12 3 3 5-6"/>',
  sliders:'<path d="M4 7h7m4 0h5M4 17h3m4 0h9"/><circle cx="13" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  terminal:'<rect x="3" y="4" width="18" height="16" rx="3"/><path d="m7 9 3 3-3 3m6 0h4"/>',
  folder:'<path d="M3 8V5a1 1 0 0 1 1-1h5l2 3h8a2 2 0 0 1 2 2v10H3V8Z"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  x:'<path d="m6 6 12 12M6 18 18 6"/>',
  arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
  chevron:'<path d="m9 5 7 7-7 7"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
  file:'<path d="M13 3H5v18h14V9l-6-6Z"/><path d="M13 3v6h6M8 13h8M8 17h5"/>',
  code:'<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  play:'<path d="m8 4 12 8-12 8V4Z"/>',
  pause:'<path d="M8 5v14M16 5v14"/>',
  spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/>',
  box:'<path d="m12 3 9 5v8l-9 5-9-5V8l9-5Zm0 10v8M3 8l9 5 9-5M7 6l10 5"/>',
  lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 4v3"/>',
  activity:'<path d="M2 12h5l3-8 4 16 3-8h5"/>',
  refresh:'<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-2l2 3M4 16l2 3a7 7 0 0 0 12-2"/>',
  copy:'<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 5V3H3v13h2"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
};
const icon = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.file}</svg>`;
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
const text = (v) => typeof v === 'object' && v !== null ? JSON.stringify(v, null, 2) : String(v ?? '');
const MILESTONES = ['INTERPRETED','FORMALIZED','TYPECHECKED','PROVED','IMPLEMENTED','LINKED','TESTED','END_TO_END_VERIFIED'];
const LABELS = ['Interpreted','Formalized','Typechecked','Proved','Implemented','Linked','Tested','End-to-end'];
const SHORT = ['INTE','FORM','TYPE','PROV','IMPL','LINK','TEST','END_'];
const state = {meta:null,runs:[],requests:[],requestError:'',editingRequest:null,detail:null,route:'runs',id:null,tab:'overview',search:'',filter:'all',artifact:null,artifactData:null,activity:'events',refreshing:false,connected:false};
let toastTimer;

function hydrateIcons(root=document) { root.querySelectorAll('[data-icon]').forEach(el => {el.innerHTML=icon(el.dataset.icon);el.removeAttribute('data-icon');}); }
function badge(value) {
  const s=String(value || 'NOT_RECORDED'), good=['PASS','VERIFIED','ACCEPTED','REVIEW_ACCEPTED'].includes(s), bad=['FAIL','INFRASTRUCTURE_FAILURE','ERROR'].includes(s), live=['RUNNING','CANCELLING'].includes(s), warn=['BLOCKED','INTERRUPTED','STOPPED','CANCELLED','INCOMPLETE'].includes(s);
  return `<span class="badge ${good?'good':bad?'bad':live?'live':warn?'warn':''}" title="${esc(s)}">${good?icon('check'):bad?icon('x'):''}${esc(s.replaceAll('_',' '))}</span>`;
}
function outcome(value) {
  const v=value || 'PENDING', cls=v==='PASS'?'pass':['FAIL','BLOCKED','INVALID'].includes(v)?'fail':v==='UNSUPPORTED'?'unavailable':v==='STALE'?'stale':v==='NOT_APPLICABLE'?'':'wait';
  return `<span class="outcome ${cls}" title="${esc(v)}" aria-label="${esc(v.replaceAll('_',' '))}">${v==='PASS'?icon('check'):['FAIL','BLOCKED','INVALID'].includes(v)?icon('x'):v==='NOT_APPLICABLE'?'—':v==='UNSUPPORTED'?'⊘':v==='STALE'?'↻':'·'}</span>`;
}
function date(value, timeOnly=false) { const d=new Date(value);return Number.isNaN(d.getTime())?'—':timeOnly?d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'}):d.toLocaleDateString([], {month:'short',day:'numeric'})+' · '+d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}); }
function bytes(n) { return n>=1048576?(n/1048576).toFixed(1)+' MB':n>=1024?(n/1024).toFixed(1)+' KB':(n||0)+' B'; }
function active(run) {return ['RUNNING','CANCELLING'].includes(run?.process_status);}
function tierLabel(run) {return Number.isInteger(run?.tier)?`TIER ${run.tier}${run.target?' · '+String(run.target).toUpperCase():''}`:'UNSPECIFIED';}
function toast(message) {$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,4000);}
function inlineError(id, message) {const el=$(id);el.textContent=message;el.hidden=!message;}

async function api(path, body, retried=false) {
  const opts={cache:'no-store',headers:{'Accept':'application/json'}};
  if(body!==undefined) {opts.method='POST';opts.headers['Content-Type']='application/json';opts.headers['X-VeriSlop-Token']=state.meta?.token || '';opts.body=JSON.stringify(body);}
  const response=await fetch(path,opts);
  let data;
  try {data=await response.json();} catch {throw new Error('The local server returned an unreadable response.');}
  if(response.status===403 && body!==undefined && !retried && data.error==='Missing or invalid workbench request token.'){
    state.meta=await api('/api/meta');
    return api(path,body,true);
  }
  if(!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}
function connection(ok,error='') {
  state.connected=ok;$('#connection-dot').classList.toggle('online',ok);$('#connection-label').textContent=ok?'Local CLI connected':'Connection lost';
  $('#connection-error').hidden=ok;$('#connection-error').textContent=ok?'':`Cannot reach the local workbench. ${error} Retained results below may be stale.`;
}
function showDialog(id) {const d=$(id);if(!d.open)d.showModal();}
function route() {
  const [section,ident]=location.hash.replace(/^#\/?/,'').split('/');
  const id=section==='runs'&&ident?decodeURIComponent(ident):null;
  if(id!==state.id){state.detail=null;state.tab='overview';state.artifact=null;state.artifactData=null;state.activity='events';}
  state.id=id;state.route=['runs','capabilities','setup'].includes(section)?section:'runs';
  document.querySelectorAll('[data-nav]').forEach(el=>{if(el.dataset.nav===state.route)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
  $('#breadcrumb-current').textContent=id?'Run details':{runs:'Runs',capabilities:'Assurance tiers',setup:'Local setup'}[state.route];
  render();refresh();
}
async function refresh() {
  if(state.refreshing || !state.meta)return;
  state.refreshing=true;
  const current=state.id;
  try {
    const [listResult,requestResult]=await Promise.allSettled([api('/api/runs'),api('/api/requests')]);
    if(listResult.status==='rejected')throw listResult.reason;
    const runs=listResult.value.runs || [], previousRequestError=state.requestError;
    const runsChanged=JSON.stringify(runs)!==JSON.stringify(state.runs);
    let requestsChanged=false;
    if(requestResult.status==='fulfilled'){
      const requests=requestResult.value.requests || [];
      requestsChanged=JSON.stringify(requests)!==JSON.stringify(state.requests);
      state.requests=requests;state.requestError='';
    }else state.requestError=requestResult.reason.message;
    requestsChanged=requestsChanged||previousRequestError!==state.requestError;
    state.runs=runs;$('#nav-count').textContent=state.runs.length;
    if(current) {
      const detail=await api(`/api/runs/${encodeURIComponent(current)}`);
      if(state.id===current) {
        const previous=state.detail, changed=JSON.stringify(previous)!==JSON.stringify(detail);
        state.detail=detail;
        const oldFile=previous?.artifacts?.find(f=>f.path===state.artifact),newFile=detail.artifacts?.find(f=>f.path===state.artifact);
        if(JSON.stringify(oldFile)!==JSON.stringify(newFile))state.artifactData=null;
        if(state.route==='runs'&&changed){
          const keepPreview=state.tab==='artifacts'&&previous&&JSON.stringify(previous.artifacts)===JSON.stringify(detail.artifacts)&&previous.run?.process_status===detail.run?.process_status;
          renderDetail(state.tab==='artifacts'?keepPreview:true);
        }
        if(state.route==='runs'&&state.tab==='artifacts'&&active(detail.run)&&state.artifact)loadArtifact();
      }
    } else if(state.route==='runs'&&(runsChanged||requestsChanged))renderRuns();
    connection(true);
  } catch(e) {
    connection(false,e.message);
    if(state.id===current && current && !state.detail)$('#main').innerHTML=`<a class="back-link" href="#/runs">${icon('arrow')}All runs</a><div class="callout bad">${esc(e.message)}</div>`;
  } finally {state.refreshing=false;}
}
function render() {
  if(state.route==='capabilities')renderCapabilities();
  else if(state.route==='setup')renderSetup();
  else if(state.id){if(state.detail)renderDetail();else $('#main').innerHTML='<div class="loading"><span class="spinner"></span> Reading the run package…</div>';}
  else renderRuns();
}
function renderRuns() {
  if($('#search-input') && document.activeElement===$('#search-input')){renderRows();renderRequests();return;}
  const running=state.runs.filter(active).length, verified=state.runs.filter(r=>r.status==='VERIFIED').length;
  $('#main').innerHTML=`<div class="page-heading"><div><p class="eyebrow">THE VERIFICATION WORKSPACE</p><h1>Runs & evidence.</h1><p>Start with a request. Follow every obligation through the pipeline.</p></div><span class="heading-symbol" aria-hidden="true">⊢</span></div>
    <section class="metrics" aria-label="Run statistics"><div class="metric"><div class="metric-label">Total runs ${icon('layers')}</div><div class="metric-value">${state.runs.length}<small>in this workspace</small></div></div><div class="metric"><div class="metric-label">Active now ${icon('activity')}</div><div class="metric-value">${running}<small>${running?'CLI process running':'ready for your next request'}</small></div></div><div class="metric"><div class="metric-label">Recorded verified ${icon('shield')}</div><div class="metric-value green">${verified}<small>within declared endpoints</small></div></div></section>
    <section class="panel request-panel" aria-label="Saved requests"><div class="section-head"><div><div class="section-title"><h3>Saved requests</h3><span id="request-count" class="count-label">${state.requests.length}</span></div><p class="field-hint">Write now. Launch when you’re ready.</p></div><button class="button secondary" data-action="new-run">${icon('plus')} Add request</button></div><div id="request-rows"></div></section>
    <section class="panel"><div class="section-head"><div class="section-title"><h3>Verification runs</h3><span class="count-label">${state.runs.length}</span></div><div class="filters"><label class="search">${icon('search')}<span class="sr-only">Search runs</span><input id="search-input" type="search" placeholder="Find a run…" value="${esc(state.search)}"></label><select id="status-filter" aria-label="Filter runs by status"><option value="all">All statuses</option><option value="running">Running</option><option value="verified">Verified</option><option value="blocked">Blocked</option><option value="other">Other results</option></select></div></div><div id="run-rows"></div><div class="bottom-note"><span>${icon('info')}Recorded outcomes describe the selected run and its assurance endpoint.</span><button class="text-button" data-action="refresh">${icon('refresh')} Refresh</button></div></section>
    <div class="getting-started"><button data-action="example"><span>${icon('box')}</span><div><h3>A first run, without model setup.</h3><p>Try the bundled Python example through the real Lean and testing pipeline.</p></div>${icon('arrow')}</button><button data-action="setup"><span>${icon('sliders')}</span><div><h3>Your models. Your workflow.</h3><p>Use local Ollama or your existing provider and adversarial-review configuration.</p></div>${icon('arrow')}</button></div>`;
  $('#status-filter').value=state.filter;renderRows();renderRequests();
}
function renderRequests() {
  const root=$('#request-rows');if(!root)return;
  $('#request-count').textContent=state.requests.length;
  root.innerHTML=state.requests.length?state.requests.map(r=>`<article class="request-row"><div class="request-copy"><p>${esc(r.prompt || r.prompt_preview || 'Software request')}</p><div class="request-meta"><span class="badge">${r.last_run_id?'SAVED · PREVIOUSLY LAUNCHED':'SAVED REQUEST'}</span><span>Tier ${esc(r.tier)}</span><span>Updated ${esc(date(r.updated_at))}</span></div><small>${esc(r.config || 'Choose a provider configuration when you’re ready to launch.')}</small></div><div class="request-actions"><button class="button secondary" data-action="edit-request" data-id="${esc(r.id)}">Edit request ${icon('arrow')}</button>${r.last_run_id?`<button class="text-button" data-action="select-run" data-id="${esc(r.last_run_id)}">View last run ${icon('chevron')}</button>`:''}</div></article>`).join(''):`<div class="request-empty"><span class="run-icon">${icon('file')}</span><div><h3>What would you like to build?</h3><p>Add a software request in your own words. You can save it before setting up models.</p></div><button class="text-button" data-action="new-run">Write a request ${icon('arrow')}</button></div>`;
  if(state.requestError)root.innerHTML=`<div class="callout" role="status"><strong>Saved requests unavailable</strong><p>${esc(state.requestError)}</p><p>Previously loaded requests may be stale. Run inspection remains available.</p></div>`+(state.requests.length?root.innerHTML:'');
}
function renderRows() {
  const dest=$('#run-rows');if(!dest)return;
  const query=state.search.toLowerCase();
  const runs=state.runs.filter(r=>(`${r.run_id} ${r.prompt} ${r.path}`).toLowerCase().includes(query)).filter(r=>state.filter==='all'||(state.filter==='running'?active(r):state.filter==='verified'?r.status==='VERIFIED':state.filter==='blocked'?r.status==='BLOCKED':!active(r)&&!['VERIFIED','BLOCKED'].includes(r.status)));
  if(!runs.length){dest.innerHTML=state.runs.length?`<div class="empty-state compact"><h3>No matching runs.</h3><p>Try a different search or status.</p><button class="text-button" data-action="clear-filters">Clear filters</button></div>`:`<div class="empty-state"><div class="empty-illustration" aria-hidden="true"><div class="diagram-node">${icon('file')}</div><span class="diagram-line"></span><div class="diagram-node middle">${icon('shield')}</div><span class="diagram-line"></span><div class="diagram-node">${icon('code')}</div></div><h3>Your next idea starts here.</h3><p>Turn a software specification into a traceable run.<br>Keep the contract, proofs, and implementation in view.</p><div class="empty-actions"><button class="button primary" data-action="new-run">${icon('plus')} Add your first request</button><button class="button quiet" data-action="open-package">Open existing evidence ${icon('arrow')}</button></div></div>`;return;}
  dest.innerHTML=`<div class="run-columns"><span>REQUEST / RUN</span><span>ASSURANCE</span><span>STATUS</span><span class="date-column">CREATED</span><span></span></div>`+runs.map(r=>`<button class="run-row" data-action="select-run" data-id="${esc(r.id)}" aria-label="Open ${esc(r.run_id)}"><div class="run-name"><span class="run-icon">${icon(active(r)?'activity':'file')}</span><div><strong>${esc((r.prompt || r.run_id || 'Untitled run').split('\n')[0])}</strong><small>${esc(r.run_id)}</small></div></div><div class="run-tier">${esc(tierLabel(r))}</div><div>${badge(r.status)}</div><div class="run-date">${esc(date(r.created_at))}</div>${icon('chevron')}</button>`).join('');
}
function renderDetail(poll=false) {
  const d=state.detail,r=d?.run;if(!r)return;
  // Artifact previews stay in place while events continue polling.
  if(poll && $('#detail-body')){const badgeNode=$('#run-status');if(badgeNode)badgeNode.innerHTML=badge(r.status);if(state.tab==='artifacts')return;}
  const previousScroll=$('.activity-body')?.scrollTop || 0;
  const focused=document.activeElement?.id;
  $('#main').innerHTML=`<a class="back-link" href="#/runs">${icon('arrow')} All verification runs</a><div class="page-heading detail-heading"><div><p class="eyebrow">RUN / ${esc(tierLabel(r))}</p><h1 class="run-title">${esc(r.run_id)}</h1><div class="subline"><span id="run-status">${badge(r.status)}</span><span>${esc(date(r.created_at))}</span><span class="process-label">${r.process_status==='NOT_OWNED'?'Historical package · process not managed here':'Process: '+esc((r.process_status||'unknown').toLowerCase())+(typeof r.exit_code==='number'?' · exit '+esc(r.exit_code):'')}</span>${r.mode==='example'?'<span>Bundled offline example</span>':''}${active(r)?`<span>Stage: ${esc(r.phase || 'starting')}</span>`:''}</div></div>${r.owned && active(r)?`<button class="button secondary" data-action="cancel">${icon('pause')} Stop run</button>`:`<button class="button secondary" data-action="refresh">${icon('refresh')} Refresh</button>`}</div>
    <section class="panel"><div class="detail-summary"><div><div class="label">Mechanical closure</div><div class="summary-value">${badge(r.mechanical_status)}</div></div><div><div class="label">Release review</div><div class="summary-value">${badge(r.release_status)}</div></div><div><div class="label">Declared target</div><div class="summary-value">${esc(d.report?.tier?.require_state || r.require_state || 'Not recorded')}<br><span class="field-hint">${esc(d.report?.tier?.endpoint || r.endpoint || 'No endpoint recorded')}</span></div></div></div><div class="historical-note">${icon('info')}Recorded artifacts, not a fresh verification. Process progress does not award obligation milestones.</div></section>
    <div class="tabs" role="tablist" aria-label="Run details">${[['overview','layers','Overview'],['obligations','shield','Obligations'],['artifacts','folder','Artifacts'],['activity','activity','Activity']].map(([key,ic,label])=>`<button class="tab" role="tab" id="tab-${key}" aria-controls="detail-body" aria-selected="${state.tab===key}" tabindex="${state.tab===key?'0':'-1'}" data-action="tab" data-tab="${key}">${icon(ic)}${label}${key==='obligations'?`<span class="count-label">${(d.obligations||[]).length}</span>`:''}</button>`).join('')}</div><section id="detail-body" role="tabpanel" aria-labelledby="tab-${state.tab}"></section>`;
  if(state.tab==='overview')renderOverview();else if(state.tab==='obligations')renderObligations();else if(state.tab==='artifacts')renderArtifacts();else renderActivity();
  if(poll && $('.activity-body'))$('.activity-body').scrollTop=previousScroll;
  if(poll && focused && document.getElementById(focused))document.getElementById(focused).focus({preventScroll:true});
}
function pipeline(obligations) {
  return `<div class="pipeline" aria-label="Recorded obligation milestones">${MILESTONES.map((m,i)=>{
    const applicable=obligations.filter(o=>o.outcomes?.[m]!=='NOT_APPLICABLE'),passed=applicable.filter(o=>o.outcomes?.[m]==='PASS').length;
    const unsupported=applicable.length>0&&applicable.every(o=>o.outcomes?.[m]==='UNSUPPORTED');
    return `<div class="milestone"><span class="milestone-dot ${passed&&passed===applicable.length?'passed':passed?'partial':''}">${unsupported?'⊘':passed&&passed===applicable.length?icon('check'):String(i+1).padStart(2,'0')}</span><strong>${LABELS[i].toUpperCase()}</strong><small>${unsupported?'Unsupported':applicable.length?`${passed} / ${applicable.length}`:'—'}</small></div>`;
  }).join('')}</div>`;
}
function eventRows(events) {return events.map(e=>`<li class="event"><time>${esc(date(e.time,true))}</time><span class="event-icon ${e.outcome==='PASS'?'good':['FAIL','BLOCKED'].includes(e.outcome)?'bad':''}">${icon(e.outcome==='PASS'?'check':e.type==='diagnostic'?'info':e.type==='stage_started'?'play':'activity')}</span><div><small>${esc(e.phase || e.type || 'event')}</small><p>${esc(e.message || e.code || e.type || '')}</p></div></li>`).join('');}
function diagnostics() {
  const d=state.detail,report=d.report||{};
  const reasons=[...(report.blocking_reasons||[]),...(report.infrastructure_errors||[])];
  const warnings=(d.warnings||[]).filter(w=>!String(w).startsWith('Recorded artifacts are historical observations.'));
  const processWarning=['INTERRUPTED','CANCELLED'].includes(d.run.process_status)||(typeof d.run.exit_code==='number'&&d.run.exit_code!==0);
  return (processWarning?`<div class="callout"><strong>CLI process ${esc(d.run.process_status.toLowerCase())}${d.run.exit_code!==null&&d.run.exit_code!==undefined?` · exit ${esc(d.run.exit_code)}`:''}</strong><p>Process completion and the retained report are separate observations. Inspect the activity log for the exit diagnostic.</p></div>`:'')+(reasons.length?`<div class="callout"><strong>Recorded blockers</strong>${reasons.slice(0,10).map(x=>`<p><code>${esc(x.code || '')}</code> ${esc(x.message || text(x))}</p>`).join('')}</div>`:'')+(warnings.length?`<div class="callout neutral">${warnings.map(w=>`<p>${esc(text(w))}</p>`).join('')}</div>`:'');
}
function renderOverview() {
  const d=state.detail,events=d.events||[],report=d.report||{};
  $('#detail-body').innerHTML=diagnostics()+pipeline(d.obligations||[])+`<div class="section-grid"><section class="panel"><div class="section-head slim"><h3>Original specification</h3>${icon('file')}</div><div class="panel-body"><p class="request-text">${esc(d.prompt || 'The request has not been recorded yet.')}</p></div><div class="bottom-note"><span class="setup-path">${esc(d.run.path)}</span></div></section><section class="panel"><div class="section-head slim"><h3>Recent activity</h3><button class="text-button" data-action="tab" data-tab="activity">View all ${icon('arrow')}</button></div><div class="panel-body">${events.length?`<ol class="event-list">${eventRows(events.slice(-5).reverse())}</ol>`:'<p class="field-hint">Events appear here when the CLI starts working.</p>'}</div></section></div>${report.qualified_result?`<div class="callout neutral spaced"><strong>Recorded result</strong><p>${esc(text(report.qualified_result))}</p></div>`:''}`;
}
function renderObligations() {
  const obs=state.detail.obligations||[];
  $('#detail-body').innerHTML=`<div class="panel">${obs.length?`<div class="matrix-wrap"><table class="obligation-table"><thead><tr><th scope="col">ID</th><th scope="col">OBLIGATION</th>${SHORT.map((s,i)=>`<th scope="col" title="${MILESTONES[i]}">${s}</th>`).join('')}</tr></thead><tbody>${obs.map(o=>`<tr><td><button class="obligation-link" data-action="obligation" data-id="${esc(o.id)}">${esc(o.id)}</button></td><td><p title="${esc(o.statement || o.kind)}">${esc(o.statement || o.kind || 'Statement unavailable')}</p><small>${esc((o.role || o.kind || '').replaceAll('_',' '))}${o.required?' · required':''}</small></td>${MILESTONES.map(m=>`<td>${outcome(o.outcomes?.[m])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:`<div class="empty-state compact"><h3>No recorded obligations yet.</h3><p>Accepted obligations and recorded lifecycle outcomes will appear as the CLI creates their artifacts.</p></div>`}<div class="legend"><span>${outcome('PASS')} Pass</span><span>${outcome('FAIL')} Failed / blocked</span><span>${outcome('PENDING')} Pending</span><span>${outcome('STALE')} Stale</span><span>${outcome('UNSUPPORTED')} Unsupported</span><span>${outcome('NOT_APPLICABLE')} Not applicable</span></div></div><div class="callout neutral spaced">Proof, testing, and end-to-end verification are separate outcomes. Tier 2 applies to restricted source semantics; it does not establish machine-code correctness.</div>`;
}
function renderArtifacts() {
  const files=state.detail.artifacts||[];
  if(!files.length){$('#detail-body').innerHTML='<div class="panel empty-state compact"><h3>No previewable artifacts yet.</h3><p>JSON, Lean, implementation source, and evidence files will appear here.</p></div>';return;}
  if(!state.artifact){state.artifact=files.find(f=>f.path==='report.json')?.path || files[0].path;state.artifactData=null;}
  $('#detail-body').innerHTML=`<div class="artifact-layout"><div class="file-list" aria-label="Artifacts">${files.map(f=>`<button class="file-button ${state.artifact===f.path?'active':''}" data-action="artifact" data-path="${esc(f.path)}" aria-pressed="${state.artifact===f.path}">${icon(/\.(lean|py|vsc)$/.test(f.path)?'code':'file')}<span>${esc(f.path)}<small>${bytes(f.size)}</small></span></button>`).join('')}</div><div class="code-pane"><div class="code-head"><form id="artifact-path-form" class="artifact-path-form"><input id="artifact-path-input" aria-label="Artifact path" value="${esc(state.artifact)}" required autocomplete="off"><button class="text-button" type="submit">Open</button></form><button class="icon-button" data-action="copy-artifact" aria-label="Copy artifact preview">${icon('copy')}</button></div><pre id="artifact-content" tabindex="0">Loading artifact…</pre><div id="artifact-foot" class="code-foot">Read-only preview · original bytes are retained in the run package</div></div></div>`;
  if(state.artifactData?.path===state.artifact)showArtifact(state.artifactData);else loadArtifact();
}
async function loadArtifact() {
  const id=state.id,path=state.artifact;
  try {const data=await api(`/api/runs/${encodeURIComponent(id)}/artifact?path=${encodeURIComponent(path)}`);if(state.id!==id||state.artifact!==path)return;state.artifactData=data;showArtifact(data);}
  catch(e){if(state.id===id&&state.artifact===path&&$('#artifact-content'))$('#artifact-content').textContent=e.message;}
}
function showArtifact(data) {if(!$('#artifact-content'))return;let value=data.content;if(data.path.endsWith('.json')&&!data.truncated){try{value=JSON.stringify(JSON.parse(value),null,2);}catch{/* Partial JSON remains exact text. */}}$('#artifact-content').textContent=value;$('#artifact-foot').textContent=`${bytes(data.size)} · ${data.truncated?'Truncated preview; full artifact remains on disk':'Read-only preview'} · Original file unchanged`;}
function renderActivity() {
  const d=state.detail;
  $('#detail-body').innerHTML=`<div class="panel"><div class="activity-toolbar"><div class="section-title"><h3>CLI activity</h3>${active(d.run)?'<span class="badge live">LIVE</span>':'<span class="count-label">RECORDED</span>'}</div><select id="activity-select" aria-label="Activity source"><option value="events">Structured events</option><option value="stderr">Process log</option><option value="stdout">CLI result</option><option value="command">Launch command</option></select></div><div id="activity-content"></div></div>`;
  $('#activity-select').value=state.activity;renderActivityContent();
}
function renderActivityContent() {
  const d=state.detail,container=$('#activity-content');if(!container)return;
  if(state.activity==='events')container.innerHTML=`<div class="activity-body">${d.events?.length?`<ol class="event-list">${eventRows(d.events)}</ol>`:'<div class="empty-state compact"><h3>Waiting for activity.</h3><p>The CLI event stream will appear here.</p></div>'}</div>`;
  else {const content=state.activity==='command'?(Array.isArray(d.command)?d.command.map(x=>/^[\w./:=+-]+$/.test(x)?x:JSON.stringify(x)).join(' '):text(d.command)):d[state.activity];container.innerHTML=`<pre class="logs" tabindex="0">${esc(content || 'No content recorded.')}</pre>`;}
}
function obligationDetail(id) {
  const o=(state.detail.obligations||[]).find(x=>x.id===id);if(!o)return;
  $('#obligation-title').textContent=`${o.id} · ${(o.kind || o.role || 'obligation').replaceAll('_',' ')}`;
  $('#obligation-detail').innerHTML=`<div class="detail-item"><div class="label">Statement</div><p>${esc(o.statement || 'Statement unavailable in the retained view.')}</p></div><div class="outcome-list">${MILESTONES.map((m,i)=>`<div>${outcome(o.outcomes?.[m])}${LABELS[i]}</div>`).join('')}</div>${[['Current state',o.state],['Proof boundary',o.proof_boundary],['Implementation assurance',o.implementation_assurance],['Formal symbol',o.lean_symbol || o.formal?.lean_symbol],['Blocking reasons',o.blocking?.length?o.blocking:null]].filter(([,v])=>v).map(([label,value])=>`<div class="detail-item"><div class="label">${label}</div><p>${esc(text(value))}</p></div>`).join('')}`;
  showDialog('#obligation-dialog');
}
function renderCapabilities() {
  $('#main').innerHTML=`<div class="page-heading"><div><p class="eyebrow">KNOW THE BOUNDARY</p><h1>Choose the right assurance.</h1><p>Each tier establishes a different relationship between the contract and the implementation.</p></div><span class="heading-symbol" aria-hidden="true">⊨</span></div><div class="tier-grid">${[
    [0,'Property testing','Generate and execute a finite Python test campaign from the accepted contract. Passing tests establish the recorded TESTED result.','TESTED'],
    [1,'Runtime contracts','Instrument Python with runtime assertions and run the test campaign. Assertions detect supported violations during execution.','TESTED + ASSERTIONS'],
    [2,'Source verification','Verify VSCore 0.3 source semantics against the accepted Lean contract, including the bridge and required closure checks.','RESTRICTED SOURCE']
  ].map(([n,title,desc,tag])=>`<section class="tier-card"><div class="tier-number">TIER / 0${n}</div><h2>${title}</h2><p>${desc}</p><span class="badge good">${icon('check')} ${tag}</span><button class="text-button" data-action="new-tier" data-tier="${n}">Configure a run ${icon('arrow')}</button></section>`).join('')}</div><div class="panel"><div class="section-head"><h3>Explicit limits, visible evidence.</h3>${icon('shield')}</div><div class="boundaries"><div><h3>Tiers 3 and 4 are unavailable</h3><p>Verified extraction and machine-code verification remain unsupported. This app does not substitute a lower tier for either one.</p></div><div><h3>Tests and proofs are distinct</h3><p>Tier 2 runtime campaigns are unavailable. Its end-to-end claim applies to the restricted source endpoint, not an interpreter, deployed service, compiler, or machine code.</p></div><div><h3>The CLI decides outcomes</h3><p>Model proposals and progress events are not proof authority. The workbench displays recorded obligation outcomes and the report's declared endpoint.</p></div><div><h3>Review remains a separate gate</h3><p>A mechanical proof may pass while release review remains blocked. Both results stay visible in the run details.</p></div></div></div>`;
}
function renderSetup() {
  const m=state.meta||{},e=m.environment||{};
  $('#main').innerHTML=`<div class="page-heading"><div><p class="eyebrow">LOCAL BY DESIGN</p><h1>Your workspace. Your models.</h1><p>Use existing CLI configurations and credentials. Nothing is launched until you choose to run it.</p></div></div><div class="setup-grid"><section class="panel"><div class="section-head slim"><h3>Workspace environment</h3>${icon('terminal')}</div><div class="panel-body"><div class="label">Workspace root</div><p class="setup-path">${esc(m.workspace)}</p><div class="label">New run packages</div><p class="setup-path">${esc(m.runs_dir)}</p><div class="setup-status"><strong>Python</strong><code>${esc(e.python || 'See CLI doctor')}</code></div><div class="setup-status"><strong>Pinned Lean toolchain</strong>${badge(e.lean_installed?'AVAILABLE':'NOT FOUND')}</div><div class="setup-status"><strong>Linux bubblewrap</strong>${badge(e.bubblewrap_installed?'AVAILABLE':'NOT FOUND')}</div><p class="field-hint spaced">Presence checks only. Use CLI doctor to check the toolchain and containment prerequisites.</p><pre class="command-block">python -m verislop doctor</pre></div></section><section class="panel"><div class="section-head slim"><h3>Model & review configuration</h3>${icon('sliders')}</div><div class="panel-body"><p>Select an existing provider JSON file when launching a run. It controls interpretation, proof routing, implementation, and adversarial review agents.</p><p>Ollama model names are user-selected in that configuration or its referenced environment variables. Cloud providers use the CLI's credential references.</p><pre class="command-block">python -m verislop providers check \\\n  --config examples/ollama-review-config.json</pre><p class="field-hint">Set required environment variables in the terminal that starts the workbench. Credentials are not entered or stored in the browser.</p></div></section><section class="panel"><div class="section-head slim"><h3>Available configuration paths</h3><span class="count-label">${(m.configs||[]).length}</span></div><div class="panel-body">${m.configs?.length?`<ul class="config-list">${m.configs.map(c=>{const path=typeof c==='string'?c:c.path,info=(m.config_details||[]).find(d=>d.path===path);return `<li><span>${esc(path)}${info?.valid?`<small>Tier ${esc(info.tier)} · ${esc(info.endpoint||'declared endpoint')}</small>`:''}</span><button class="text-button" data-action="use-config" data-path="${esc(path)}" aria-label="Use ${esc(path)}" ${info&&(!info.valid||![0,1,2].includes(info.tier))?'disabled title="Configuration is invalid or requests an unsupported tier"':''}>Use ${icon('arrow')}</button></li>`;}).join('')}</ul>`:'<p>No example configurations found. Enter your workspace-relative configuration path in the request form.</p>'}<button class="text-button" data-action="new-run">Use a configuration ${icon('arrow')}</button></div></section><section class="panel"><div class="section-head slim"><h3>Inspect retained evidence</h3>${icon('folder')}</div><div class="panel-body"><p>Packages directly under the runs directory appear automatically. Open a package elsewhere in this workspace by its path.</p><p>Opening evidence does not resume a run, call a model, or reverify a historical result.</p><button class="button secondary" data-action="open-package">${icon('folder')} Open existing package</button></div></section></div>`;
}
function updateRunMode() {
  const example=$('#new-run-form').elements.mode.value==='example';
  $('#agent-fields').hidden=example;$('#example-fields').hidden=!example;$('#prompt-input').required=!example;
  $('#new-run-title').textContent=example?'Try the offline example.':state.editingRequest?'Edit your software request.':'Add a software request.';
  $('#save-request-button').hidden=example;
  $('#launch-button').innerHTML=icon('play')+(example?' Launch run':' Save & launch');
  $('#launch-button').classList.toggle('primary',example);$('#launch-button').classList.toggle('secondary',!example);
  $('#tier-input').disabled=example;if(example)$('#tier-input').value='0';
  $('#launch-note').textContent=example?'No model calls · real native checks':'Saved locally · runs only when launched';
  const n=Number($('#tier-input').value);
  $('#target-note').textContent=n===2?'VSCore 0.3 · restricted_source. Runtime TESTED campaigns are unavailable.':'Python · '+(n===1?'instrumented_runtime with runtime assertions and a test campaign.':'test_campaign. Finite testing does not establish universal correctness.');
  updatePromptSize();updateConfigHint();
}
function updateConfigHint() {
  const path=$('#config-input').value, info=(state.meta?.config_details||[]).find(c=>c.path===path);
  const hint=$('#config-hint');hint.hidden=!info;hint.classList.remove('config-warning');
  if(!info)return;
  const unsupported=info.valid&&![0,1,2].includes(info.tier),mismatch=info.valid&&info.tier!==Number($('#tier-input').value);
  hint.textContent=!info.valid?'This file could not be validated. Check the provider configuration before launch.':unsupported?`This configuration requests Tier ${info.tier}, which is unavailable in this MVP. Choose a supported configuration.`:mismatch?`This configuration requires Tier ${info.tier}. Select that assurance target to launch with it.`:`Configured for Tier ${info.tier}${info.endpoint?' · '+info.endpoint:''}. Credentials and model availability are checked at launch.`;
  hint.classList.toggle('config-warning',!info.valid||mismatch);
}
function updatePromptSize() {
  const size=new TextEncoder().encode($('#prompt-input').value).length;
  $('#prompt-size').textContent=`${size.toLocaleString()} / 64,000 UTF-8 bytes`;
  $('#prompt-input').setCustomValidity($('#new-run-form').elements.mode.value!=='example'&&size>64000?'Keep the software request within 64,000 UTF-8 bytes.':'');
}
function openNew(mode='agents',tier=0) {
  if(!state.meta){toast('Wait for the local server to connect.');return;}
  state.editingRequest=null;$('#new-run-form').reset();
  $('#new-run-form').elements.mode.value=mode;$('#tier-input').value=String(tier);inlineError('#launch-error','');updateRunMode();showDialog('#new-run-dialog');
  if(mode==='agents')$('#prompt-input').focus();
}
async function editRequest(id) {
  try {
    const request=await api('/api/requests/'+encodeURIComponent(id));
    const form=$('#new-run-form');form.reset();state.editingRequest=request.id;
    form.elements.mode.value='agents';$('#prompt-input').value=request.prompt;
    $('#config-input').value=request.config || '';$('#tier-input').value=String(request.tier);
    form.elements.budget_seconds.value=request.budget_seconds;form.elements.repair_rounds.value=request.repair_rounds;
    inlineError('#launch-error','');updateRunMode();showDialog('#new-run-dialog');$('#prompt-input').focus();
  }catch(e){toast(e.message);}
}
document.addEventListener('click',async(event)=>{
  const close=event.target.closest('[data-close]');if(close){$('#'+close.dataset.close).close();return;}
  const button=event.target.closest('[data-action]');if(!button)return;
  const a=button.dataset.action;
  if(a==='new-run')openNew();
  else if(a==='use-config'){
    const info=(state.meta?.config_details||[]).find(c=>c.path===button.dataset.path);
    if(info&&(!info.valid||![0,1,2].includes(info.tier))){toast('Choose a valid configuration for Tier 0, 1, or 2.');return;}
    openNew('agents',info?.tier ?? 0);
    $('#config-input').value=button.dataset.path;updateConfigHint();
  }
  else if(a==='edit-request')await editRequest(button.dataset.id);
  else if(a==='new-tier')openNew('agents',Number(button.dataset.tier));
  else if(a==='example')openNew('example');
  else if(a==='setup')location.hash='/setup';
  else if(a==='open-package'){inlineError('#open-error','');showDialog('#open-dialog');}
  else if(a==='select-run')location.hash='/runs/'+encodeURIComponent(button.dataset.id);
  else if(a==='refresh'){await refresh();if(state.connected)toast('Workspace refreshed.');}
  else if(a==='clear-filters'){state.search='';state.filter='all';renderRuns();}
  else if(a==='tab'){state.tab=button.dataset.tab;renderDetail();}
  else if(a==='obligation')obligationDetail(button.dataset.id);
  else if(a==='artifact'){state.artifact=button.dataset.path;state.artifactData=null;renderArtifacts();}
  else if(a==='copy-artifact'){
    const value=$('#artifact-content')?.textContent;
    if(value){try{await navigator.clipboard.writeText(value);toast('Artifact preview copied.');}catch{toast('Clipboard unavailable. Select the preview text to copy it.');}}
  }
  else if(a==='cancel'){inlineError('#cancel-error','');showDialog('#cancel-dialog');}
  else if(a==='confirm-cancel'){
    button.disabled=true;
    try{await api(`/api/runs/${encodeURIComponent(state.id)}/cancel`,{});$('#cancel-dialog').close();toast('Interrupt requested. Retaining run artifacts.');await refresh();}
    catch(e){inlineError('#cancel-error',e.message);}finally{button.disabled=false;}
  }
});
document.addEventListener('input',e=>{if(e.target.id==='search-input'){state.search=e.target.value;renderRows();}if(e.target.id==='prompt-input')updatePromptSize();if(e.target.id==='config-input')updateConfigHint();});
document.addEventListener('change',e=>{
  if(e.target.id==='status-filter'){state.filter=e.target.value;renderRows();}
  if(e.target.id==='activity-select'){state.activity=e.target.value;renderActivityContent();}
  if(e.target.name==='mode'||e.target.id==='tier-input')updateRunMode();
});
document.addEventListener('submit',e=>{
  if(e.target.id==='artifact-path-form'){
    e.preventDefault();state.artifact=$('#artifact-path-input').value.trim();state.artifactData=null;renderArtifacts();
  }
});
document.addEventListener('keydown',e=>{
  if(e.target.matches('[role=tab]')&&['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){
    e.preventDefault();const tabs=['overview','obligations','artifacts','activity'];let n=tabs.indexOf(state.tab);
    n=e.key==='Home'?0:e.key==='End'?3:(n+(e.key==='ArrowRight'?1:3))%4;state.tab=tabs[n];renderDetail();$('#tab-'+state.tab).focus();
  }
});
$('#new-run-form').addEventListener('submit',async e=>{
  e.preventDefault();const form=e.target,button=e.submitter || $('#save-request-button'),data=new FormData(form);inlineError('#launch-error','');
  const body={mode:data.get('mode'),prompt:data.get('prompt')||'',config:data.get('config')||'',tier:Number($('#tier-input').value),budget_seconds:Number(data.get('budget_seconds')),repair_rounds:Number(data.get('repair_rounds'))};
  const launch=body.mode==='example'||e.submitter?.value==='launch';
  if(body.mode==='agents'&&!body.prompt.trim()){inlineError('#launch-error','Describe the software you want to build.');return;}
  const controls=[...form.querySelectorAll('input,textarea,select,button')].map(el=>[el,el.disabled]);
  controls.forEach(([el])=>el.disabled=true);button.innerHTML='<span class="spinner"></span> '+(launch?'Launching…':'Saving…');
  let saved=false;
  try {
    let result;
    if(body.mode==='example')result=await api('/api/runs',body);
    else {
      const request=await api('/api/requests'+(state.editingRequest?'/'+encodeURIComponent(state.editingRequest):''),body);
      state.editingRequest=request.id;saved=true;
      if(launch){
        if(!body.config.trim())throw new Error('Select a provider configuration to launch, or close this form and configure it later.');
        result=await api('/api/requests/'+encodeURIComponent(request.id)+'/launch',{});
      }
    }
    $('#new-run-dialog').close();
    if(launch){state.detail=null;location.hash='/runs/'+encodeURIComponent(result.id);toast('Request launched in your local CLI.');}
    else {location.hash='/runs';toast('Request saved. No run has been started.');}
    await refresh();
  }
  catch(error){inlineError('#launch-error',(saved?'Request saved. ':'')+error.message);await refresh();}
  finally{controls.forEach(([el,disabled])=>el.disabled=disabled);$('#save-request-button').innerHTML=icon('file')+' Save request';updateRunMode();}
});
$('#open-form').addEventListener('submit',async e=>{
  e.preventDefault();const button=e.target.querySelector('[type=submit]');button.disabled=true;inlineError('#open-error','');
  try{const result=await api('/api/runs/open',{path:$('#package-input').value.trim()});$('#open-dialog').close();location.hash='/runs/'+encodeURIComponent(result.id);toast('Opened retained evidence.');}
  catch(error){inlineError('#open-error',error.message);}finally{button.disabled=false;}
});
window.addEventListener('hashchange',route);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
async function connect() {
  try {state.meta=await api('/api/meta');connection(true);$('#version-label').textContent=`VERISLOP ${state.meta.version || 'CLI'} · WORKBENCH`;
    $('#config-options').innerHTML=(state.meta.configs||[]).map(c=>`<option value="${esc(typeof c==='string'?c:c.path)}"></option>`).join('');route();
  } catch(e){connection(false,e.message);$('#main').innerHTML='<div class="empty-state"><h3>The workbench is offline.</h3><p>Start the local server with <code>python -m verislop.web</code>. This page will reconnect automatically.</p></div>';}
}
hydrateIcons();connect();
setInterval(()=>{if(!document.hidden){if(state.meta)refresh();else connect();}},3000);
