const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

const STORAGE_KEY = 'mindthegap-heat-check-in-workflow-v1';
const OWNERS = ['Care navigator','Housing staff','Resource partner','Clinician','Supervisor'];
const TASK_STATUSES = ['Requested','Accepted','In progress','Blocked','Support verified'];
const bandLabels = {urgent:'Urgent',high:'High',moderate:'Moderate',low:'Low',monitor:'Monitor'};
const bandOrder = ['urgent','high','moderate','low','monitor'];
const PROGRAM_LABELS = {
  ACT: 'Assertive Community Treatment (ACT)',
  HEALTH_HOME_CM: 'Health Home Care Management',
  COMMUNITY_TREATMENT: 'Community Treatment Program',
  SUPPORTIVE_HOUSING: 'Supportive Housing',
  OUTPATIENT_CLINIC: 'Outpatient Clinic',
};
function programLabel(code) {
  return PROGRAM_LABELS[code] || String(code ?? '').replaceAll('_',' ').toLowerCase().replace(/\b\w/g, ch => ch.toUpperCase());
}
const HVI_COLORS = {1:'#73a68e',2:'#b8c8a3',3:'#d7bf7d',4:'#d39568',5:'#b76c5a'};
const ZIP_CENTROIDS = {
  '10027':[40.8116,-73.9527], '10035':[40.8009,-73.9303],
  '10301':[40.6432,-74.0765], '10457':[40.8460,-73.8987],
  '10467':[40.8795,-73.8710], '11207':[40.6718,-73.8864],
  '11212':[40.6629,-73.9131], '11226':[40.6461,-73.9568],
  '11368':[40.7490,-73.8523], '11433':[40.6979,-73.7879],
};

let data = null;
let selected = null;
let filter = 'all';
let view = 'list';
let team = 'all';
let eventVisible = true;
let workflow = {schemaVersion:1, clients:{}};
let mapView = null;
let mapDataLoaded = false;
let clientMarkers = new Map();
let edChart = null;

function toast(message) {
  const node = $('#toast');
  node.textContent = message;
  node.classList.add('show');
  clearTimeout(node._timer);
  node._timer = setTimeout(() => node.classList.remove('show'), 4200);
}

function modal(title, body) {
  $('#info-title').textContent = title;
  $('#info-body').innerHTML = body;
  $('#info').showModal();
}

function ownerOptions(current) {
  return OWNERS.map(owner => `<option ${owner === current ? 'selected' : ''}>${esc(owner)}</option>`).join('');
}

function emptyClientState() {
  return {owner:null, contactPermission:'unknown', outcome:null, note:'', callCard:null, tasks:[], history:[]};
}

function stateFor(clientId) {
  workflow.clients[clientId] ||= emptyClientState();
  return workflow.clients[clientId];
}

function loadWorkflow() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (saved?.schemaVersion === 1 && saved.clients && typeof saved.clients === 'object') workflow = saved;
  } catch {
    workflow = {schemaVersion:1, clients:{}};
  }
  const valid = new Set(data.clients.map(client => client.client_id));
  for (const id of Object.keys(workflow.clients)) if (!valid.has(id)) delete workflow.clients[id];
  data.clients.forEach(client => stateFor(client.client_id));
}

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(workflow));
    return true;
  } catch {
    toast('Could not save on this device. Keep this page open and retry.');
    return false;
  }
}

function visibleClients() {
  return data.clients.filter(client => team === 'all' || client.team_id === team);
}

function openTasks(clientId) {
  return stateFor(clientId).tasks.filter(task => task.status !== 'Support verified');
}

function workflowLabel(client) {
  const state = stateFor(client.client_id);
  if (openTasks(client.client_id).length) return `${openTasks(client.client_id).length} open task${openTasks(client.client_id).length === 1 ? '' : 's'}`;
  if (state.outcome === 'Unreachable') return 'Retry needed';
  if (state.outcome === 'Declined') return 'Manual review';
  if (state.outcome === 'Reached') return 'Check-in saved';
  if (state.owner) return 'In progress';
  return 'Unclaimed';
}

function taskTotal() {
  return data.clients.reduce((sum, client) => sum + openTasks(client.client_id).length, 0);
}

function renderEvent() {
  const focus = data.clients[0]?.hazard_focus;
  const active = focus && focus.phase !== 'none';
  $('#event').innerHTML = eventVisible && active
    ? `<div class="event"><span><b><span class="status-dot warning"></span>${esc(focus.product || 'Heat hazard active')}</b> · ${esc(focus.note)}</span><span>Engine snapshot: ${esc(data.asof)}</span></div>`
    : `<div class="event inactive"><span><b>Readiness view</b> · Hazard context is hidden; engine scores remain unchanged.</span><span>Use this view between events.</span></div>`;
  $('#event-toggle').textContent = eventVisible && active ? 'View readiness' : 'Show active warning';
  $('#hazard-summary').innerHTML = active
    ? `<strong>${esc(focus.product)}</strong><span>${esc(focus.note)}</span><small>${eventVisible ? 'Active event context shown' : 'Hidden in readiness view'} · Trust ${(focus.trust * 100).toFixed(0)}%</small>`
    : '<strong>No active hazard</strong><span>All clients remain available for readiness review.</span>';
}

function render() {
  if (!data) return;
  renderEvent();
  $('#ws-eyebrow').textContent = `TEAM WORKSPACE · ${Object.keys(data.teams).length} TEAMS · ${data.clients.length} SYNTHETIC CLIENTS`;
  $('#task-count').textContent = taskTotal() ? `· ${taskTotal()}` : '';
  $$('[data-view]').forEach(button => button.classList.toggle('active', button.dataset.view === view));
  if (selected) renderCard();
  else if (view === 'tasks') renderTasks();
  else renderList();
  syncMarkerSelection();
}

function renderList() {
  const clients = visibleClients();
  const counts = Object.fromEntries(bandOrder.map(band => [band, clients.filter(client => client.band === band).length]));
  const filtered = filter === 'all' ? clients : filter === 'lowall' ? clients.filter(client => ['low','monitor'].includes(client.band)) : clients.filter(client => client.band === filter);
  $('#work').innerHTML = `
    <div class="work-head">
      <span class="eyebrow">EXPLAINED CALL LIST</span>
      <h2>Who needs a check-in?</h2>
      <p>Engine priority and care-team workflow are shown separately. Open a client to review evidence, prepare the call, and follow support through.</p>
    </div>
    <div class="queue-overview">
      <button class="queue-metric urgent ${filter === 'urgent' ? 'active' : ''}" data-filter="urgent"><b>${counts.urgent}</b><span>Urgent</span></button>
      <button class="queue-metric high ${filter === 'high' ? 'active' : ''}" data-filter="high"><b>${counts.high}</b><span>High</span></button>
      <button class="queue-metric moderate ${filter === 'moderate' ? 'active' : ''}" data-filter="moderate"><b>${counts.moderate}</b><span>Moderate</span></button>
      <button class="queue-metric low ${filter === 'lowall' ? 'active' : ''}" data-filter="lowall"><b>${counts.low + counts.monitor}</b><span>Low / Monitor</span></button>
    </div>
    <div class="tabs">
      <button data-filter="all" class="${filter === 'all' ? 'active' : ''}">All · ${clients.length}</button>
      ${bandOrder.filter(band => counts[band]).map(band => `<button data-filter="${band}" class="${filter === band ? 'active' : ''}">${bandLabels[band]} · ${counts[band]}</button>`).join('')}
    </div>
    <div class="client-list">
      ${filtered.length ? filtered.map(client => {
        const state = stateFor(client.client_id);
        return `<button class="client" data-client="${esc(client.client_id)}" data-zip="${esc(client.zip)}">
          <div class="client-top"><strong>${esc(client.client_id)} <span aria-hidden="true">↗</span></strong><div><span class="band ${client.band}">${bandLabels[client.band]}</span><span class="confidence-tag ${client.confidence_label.toLowerCase()}-conf">${esc(client.confidence_label)} data</span></div></div>
          <p>${esc(client.reasons.slice(0,2).map(reason => reason.text).join(' · ')) || 'No active factors identified'}</p>
          <small>${esc(programLabel(client.program_type))} · Age ${client.age} · ${esc(client.borough)} ${esc(client.zip)}<br>Rank #${client.rank} on ${esc(client.team_id)} · Reach ${esc(client.reach.label)} · <b>${esc(workflowLabel(client))}</b>${state.owner ? ` · ${esc(state.owner)}` : ''}</small>
        </button>`;
      }).join('') : '<div class="empty">No clients match this filter. Other bands remain available.</div>'}
    </div>
    <div class="data-note"><b>Default weights are not calibrated.</b> Engine bands come from the Python scorecard. Workflow status is browser-local demo state and never changes the clinical score.</div>`;

  $$('[data-filter]').forEach(button => button.onclick = () => {
    filter = button.dataset.filter;
    render();
  });
  $$('[data-client]').forEach(button => {
    button.onclick = () => { selected = button.dataset.client; view = 'list'; render(); requestAnimationFrame(() => $('#back')?.focus()); };
    button.onmouseenter = button.onfocus = () => highlightZip(button.dataset.zip, true);
    button.onmouseleave = button.onblur = () => highlightZip(button.dataset.zip, false);
  });
}

function evidenceSource(factor) {
  const sources = [...new Set((factor.evidence || []).map(item => item.src).filter(Boolean))];
  const latest = (factor.evidence || []).map(item => item.asof).filter(Boolean).sort().at(-1);
  return `${sources.length ? sources.join(', ') : 'Source unavailable'}${latest ? ` · ${latest}` : ''}`;
}

function renderCard() {
  const client = data.clients.find(item => item.client_id === selected);
  if (!client) { selected = null; render(); return; }
  const state = stateFor(client.client_id);
  const unknown = client.unknowns_to_ask || [];
  const topFactors = [...client.factors].sort((a,b) => Number(b.counted) - Number(a.counted) || b.expected - a.expected).slice(0,8);
  $('#work').innerHTML = `<div class="card">
    <button class="back" id="back">← Back to call list</button>
    <div class="card-title"><div><h2>${esc(client.client_id)}</h2><div class="meta-chips">${client.first_name ? `<span class="meta-chip">${esc(client.first_name)} <small>(synthetic name)</small></span>` : ''}<span class="meta-chip">${esc(programLabel(client.program_type))}</span><span class="meta-chip">Age ${client.age}</span><span class="meta-chip">${esc(client.borough)} ${esc(client.zip)}</span></div></div><button id="claim" class="${state.owner ? 'claimed' : ''}">${state.owner ? `Claimed · ${esc(state.owner)}` : 'Claim client'}</button></div>
    <div class="status-line"><span class="band ${client.band}">${bandLabels[client.band]} engine band</span><span class="confidence-tag ${client.confidence_label.toLowerCase()}-conf">${esc(client.confidence_label)} data quality</span><span class="pill">${esc(workflowLabel(client))}</span><span class="pill">Synthetic</span></div>

    <section class="reason-box">
      <h3>Why this priority?</h3>
      <div class="reason-grid">
        <p><strong>Hazard</strong>${esc(client.hazard_focus.note)} · ${client.hazard_multiplier}× multiplier</p>
        <p><strong>Why this person</strong>${esc(client.reasons.slice(0,4).map(reason => reason.text).join('. ')) || 'No active factors identified'}.</p>
        <p><strong>Priority range</strong>${client.priority.low.toFixed(1)}–${client.priority.high.toFixed(1)} · expected ${client.priority.expected.toFixed(1)} · rank #${client.rank} on ${esc(client.team_id)}</p>
        <p><strong>Still uncertain</strong>${unknown.length ? unknown.map(item => esc(item.question)).join(' ') : 'No high-impact engine unknowns.'}</p>
      </div>
      <details><summary>How scoring and confidence work</summary><p>The Python scorecard determines the engine band. Confidence combines data quality and hazard trust and is not clinical certainty. Browser-local outcomes and tasks do not re-score the engine.</p></details>
    </section>

    <div class="factgrid">
      <div class="fact ${client.cooling_status && client.cooling_status !== 'working_ac' ? 'present' : ''}"><span>Cooling</span><b>${esc(client.cooling_status || 'unknown')}</b><small>${client.cooling_asof ? `Verified ${esc(client.cooling_asof)}` : 'Verification date unavailable'}</small></div>
      <div class="fact"><span>Preferred contact</span><b>${esc(client.contact?.preferred_method || 'unknown')}</b><small>${esc(client.reach.route || 'Route unavailable')}</small></div>
      <div class="fact"><span>Housing</span><b>${esc(client.housing_type || 'unknown')}</b><small>Source shown in factor evidence</small></div>
      <div class="fact"><span>Medication record</span><b>${client.medications === null ? 'Unavailable' : client.medications.length ? esc(client.medications.join(', ')) : 'Confirmed none'}</b><small>Clinician review only · no automated medication advice</small></div>
    </div>

    <h3 class="section-title">Follow-up tasks · ${openTasks(client.client_id).length} open</h3>
    <div class="task-facts">${state.tasks.length ? state.tasks.map(t => `<div class="fact ${t.status === 'Support verified' ? '' : 'open'}"><span>${esc(t.type)}</span><b>${esc(t.status)}</b><small>${esc(t.owner)} · due ${esc(t.due)}</small></div>`).join('') : '<p class="tiny">No follow-up tasks yet.</p>'}</div>

    <details class="factor-disclosure"><summary>Review factor evidence · ${client.factors.length} factors</summary>
      <div class="factor-list">${topFactors.map(factor => `<div class="factor-row"><div><b>${esc(factor.label)}</b><small>${esc(factor.detail || 'No finding recorded')}</small></div><span class="state ${esc(factor.state)}">${esc(factor.state)}</span><small>${esc(evidenceSource(factor))}</small></div>`).join('')}</div>
    </details>

    <h3 class="section-title">Contact permission</h3>
    <label>Consent opt-in<select id="consent"><option value="unknown" ${state.contactPermission === 'unknown' ? 'selected' : ''}>Unknown — review first</option><option value="yes" ${state.contactPermission === 'yes' ? 'selected' : ''}>Confirmed for outreach</option><option value="no" ${state.contactPermission === 'no' ? 'selected' : ''}>Not confirmed</option></select></label>
    <p class="tiny">Confirm permission before outreach. This demo does not place calls or send messages.</p>

    <section class="call-prep">
      <div class="section-heading"><div><span class="eyebrow">AI CALL COPILOT</span><h3>Prepare the check-in</h3></div>${state.callCard ? '<span class="pill">Draft ready</span>' : ''}</div>
      <div id="callcard-area">${state.callCard ? renderCallCard(state.callCard) : `<p>Generate a grounded draft from this client’s engine reasons and unknowns. The AI does not rank clients, change scores, or save answers.</p><button class="primary" id="gen-card">Generate AI call brief</button>`}</div>
    </section>

    <section class="checkin-section">
      <div class="section-heading"><div><span class="eyebrow">HUMAN REVIEW</span><h3>Record the outcome</h3></div></div>
      <form id="checkin-form">
        <div class="form-grid">
          <label>Outcome<select name="outcome"><option>Reached</option><option>Unreachable</option><option>Declined</option></select></label>
          <label>Due date<input name="due" type="date" required value="2026-07-24"></label>
          <label>Default task owner<select name="taskOwner">${ownerOptions('Care navigator')}</select></label>
        </div>
        <fieldset><legend>Support identified during the call</legend>
          <label class="check"><input type="checkbox" name="need" value="Cooling support"> Cooling support</label>
          <label class="check"><input type="checkbox" name="need" value="Transportation"> Transportation</label>
          <label class="check"><input type="checkbox" name="need" value="Clinical question"> Clinician follow-up</label>
        </fieldset>
        <label>Call note<textarea name="note" rows="3" placeholder="Record only what the client confirmed. This demo stores notes in this browser.">${esc(state.note)}</textarea></label>
        <div class="form-actions"><button type="submit" class="primary">Save check-in</button><span>Consequential updates require human confirmation.</span></div>
      </form>
    </section>
  </div>`;

  $('#back').onclick = () => { selected = null; render(); };
  $('#claim').onclick = () => {
    state.owner = state.owner ? null : 'Care navigator';
    state.history.push({at:new Date().toISOString(), action:state.owner ? `Claimed by ${state.owner}` : 'Claim released'});
    persist(); render(); toast(state.owner ? 'Client claimed.' : 'Claim released.');
  };
  $('#consent').onchange = event => {
    state.contactPermission = event.target.value;
    state.history.push({at:new Date().toISOString(), action:`Contact permission set to ${state.contactPermission}`});
    persist(); toast('Contact permission saved.');
  };
  $('#gen-card')?.addEventListener('click', () => generateCallCard(client, state));
  $('#checkin-form').onsubmit = event => saveOutcome(event, client, state);
}

function renderCallCard(card) {
  const questions = Array.isArray(card.questions) ? card.questions : [];
  return `<div class="callcard-box">
    <div class="callcard-block"><small>Suggested opening</small><p>${esc(card.greeting || 'Opening unavailable.')}</p></div>
    <div class="callcard-questions"><small>Questions to confirm</small>${questions.map((question,index) => `<div class="callcard-question"><b>${index + 1}</b><div><p>${esc(question.question)}</p><small>${esc(question.why_asking || '')}</small>${question.follow_up_if_yes ? `<details><summary>Suggested follow-up</summary><p>${esc(question.follow_up_if_yes)}</p>${question.follow_up_if_no ? `<p>${esc(question.follow_up_if_no)}</p>` : ''}</details>` : ''}</div></div>`).join('')}</div>
    <div class="callcard-block"><small>Suggested closing</small><p>${esc(card.closing || 'Closing unavailable.')}</p></div>
    <p class="tiny"><b>AI draft:</b> grounded in the current score snapshot. Review before use; it cannot update the record or provide medication advice.</p>
  </div>`;
}

async function generateCallCard(client, state) {
  const button = $('#gen-card');
  button.disabled = true;
  button.textContent = 'Generating grounded draft…';
  try {
    const response = await fetch(`/api/callcard/${encodeURIComponent(client.client_id)}`, {method:'POST'});
    if (!response.ok) throw new Error('Call card request failed');
    const card = await response.json();
    if (!Array.isArray(card.questions)) throw new Error('Call card response was incomplete');
    state.callCard = card;
    persist(); render(); toast('AI call brief generated. Review it before use.');
  } catch (error) {
    button.disabled = false;
    button.textContent = 'Retry AI call brief';
    toast('Could not generate the call brief. The scored client record is still available.');
    console.error(error);
  }
}

function addTask(state, type, owner, due) {
  const existing = state.tasks.find(task => task.type === type && task.status !== 'Support verified');
  if (existing) return;
  state.tasks.push({id:crypto.randomUUID?.() || `${Date.now()}-${type}`, type, owner, due, status:'Requested', evidence:''});
}

function saveOutcome(event, client, state) {
  event.preventDefault();
  if (!state.owner) { toast('Claim this client before saving a check-in.'); return; }
  const form = new FormData(event.currentTarget);
  state.note = String(form.get('note') || '');
  const outcome = String(form.get('outcome'));
  const due = String(form.get('due'));
  const owner = String(form.get('taskOwner'));
  if (state.contactPermission !== 'yes') {
    state.outcome = 'Permission review';
    addTask(state, 'Contact permission review', 'Supervisor', due);
    state.history.push({at:new Date().toISOString(), action:'Contact permission sent for review'});
    persist(); render(); toast('Permission review saved. No outreach outcome recorded.'); return;
  }
  state.outcome = outcome;
  if (outcome === 'Reached') [...form.getAll('need')].forEach(type => addTask(state, String(type), owner, due));
  if (outcome === 'Unreachable') addTask(state, 'Retry / escalation', 'Care navigator', due);
  if (outcome === 'Declined') addTask(state, 'Contact preference review', 'Supervisor', due);
  state.history.push({at:new Date().toISOString(), action:`${outcome} outcome saved`});
  persist(); selected = null; view = state.tasks.length ? 'tasks' : 'list'; render();
  toast('Check-in saved. Review follow-up before marking support verified.');
}

function renderTasks() {
  const taskRows = visibleClients().flatMap(client => stateFor(client.client_id).tasks.map((task,index) => ({client,task,index})));
  $('#work').innerHTML = `<div class="work-head"><span class="eyebrow">CLOSED-LOOP FOLLOW-UP</span><h2>Follow support through</h2><p>Requested is not completed. Record evidence before marking support verified.</p></div>
    <div class="task-list">${taskRows.length ? taskRows.map(({client,task,index}) => `<form class="task" data-task="${esc(client.client_id)}:${index}">
      <div class="task-head"><div><span class="eyebrow">${esc(client.client_id)}</span><h3>${esc(task.type)}</h3></div><span class="pill">${esc(task.status)}</span></div>
      <div class="form-grid"><label>Owner<select name="owner">${ownerOptions(task.owner)}</select></label><label>Due<input type="date" name="due" value="${esc(task.due)}" required></label><label>Status<select name="status">${TASK_STATUSES.map(status => `<option ${status === task.status ? 'selected' : ''}>${status}</option>`).join('')}</select></label><label>Evidence or blocker<input name="evidence" value="${esc(task.evidence)}" placeholder="How was support confirmed?"></label></div>
      <button type="submit">Save task</button>
    </form>`).join('') : '<div class="empty"><b>No follow-up tasks yet.</b><span>Open a client, claim the case, and save an outreach outcome to create one.</span></div>'}</div>`;
  $$('.task').forEach(form => form.onsubmit = event => {
    event.preventDefault();
    const [clientId,index] = form.dataset.task.split(':');
    const task = stateFor(clientId).tasks[Number(index)];
    const values = new FormData(form);
    const nextStatus = String(values.get('status'));
    const evidence = String(values.get('evidence') || '').trim();
    if (['Blocked','Support verified'].includes(nextStatus) && !evidence) { toast('Add verification evidence or a blocker before saving.'); return; }
    Object.assign(task, {owner:String(values.get('owner')), due:String(values.get('due')), status:nextStatus, evidence});
    stateFor(clientId).history.push({at:new Date().toISOString(), action:`${task.type}: ${task.status}`});
    persist(); render(); toast('Follow-up task updated.');
  });
}

async function initMap() {
  if (mapDataLoaded || typeof L === 'undefined') return;
  mapDataLoaded = true;
  const [geoResponse,hviResponse,edResponse] = await Promise.all([
    fetch('/data/nta-geo.json'), fetch('/data/hvi.json'), fetch('/data/heat-ed-visits.json')
  ]);
  const [geoData,hviData,edData] = await Promise.all([geoResponse.json(),hviResponse.json(),edResponse.json()]);
  const hviLookup = new Map(hviData.map(item => [item.ntaCode,item]));
  mapView = L.map('nta-map',{zoomControl:false,scrollWheelZoom:false}).setView([40.7128,-73.95],10);
  L.control.zoom({position:'topright'}).addTo(mapView);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OpenStreetMap contributors',maxZoom:18}).addTo(mapView);
  L.geoJSON(geoData,{style(feature){const hvi=hviLookup.get(feature.properties.ntaCode);const rank=hvi?.hviRank||0;return {fillColor:rank?HVI_COLORS[rank]:'#d6dfd8',weight:1,opacity:.75,color:'#fff',fillOpacity:rank>=4?.56:.34};},onEachFeature(feature,layer){const hvi=hviLookup.get(feature.properties.ntaCode);layer.bindPopup(`<strong>${esc(feature.properties.name)}</strong><span class="popup-borough">${esc(feature.properties.borough)}</span>${hvi?`<div class="popup-stats"><span>HVI <b>${hvi.hviRank}/5</b></span><span>AC access <b>${hvi.pctAC}%</b></span><span>Surface temp <b>${hvi.surfaceTemp}°F</b></span><span>Green space <b>${hvi.greenspace}%</b></span></div>`:''}`);}}).addTo(mapView);
  const byZip = Object.groupBy ? Object.groupBy(data.clients,client => client.zip) : data.clients.reduce((result,client) => ((result[client.zip] ||= []).push(client),result),{});
  Object.entries(byZip).forEach(([zip,clients]) => {
    const coords = ZIP_CENTROIDS[zip]; if (!coords) return;
    const marker = L.circleMarker(coords,{radius:6+clients.length,fillColor:'#0284c7',color:'#fff',weight:2,fillOpacity:.88}).addTo(mapView);
    clientMarkers.set(zip,marker);
    marker.bindPopup(`<strong>ZIP ${esc(zip)}</strong><span class="popup-borough">Approximate synthetic location · ${clients.length} client${clients.length===1?'':'s'}</span>${clients.map(client=>`<div class="popup-client"><button data-map-client="${esc(client.client_id)}">${esc(client.client_id)} · ${bandLabels[client.band]}</button></div>`).join('')}`);
    marker.on('popupopen',()=>$$('[data-map-client]').forEach(button=>button.onclick=()=>{selected=button.dataset.mapClient;view='list';render();}));
  });
  renderEdChart(edData);
  setTimeout(()=>mapView.invalidateSize(),80);
}

// A ZIP's marker turns red and grows on hover, and stays that way for as
// long as a client from that ZIP is open in the detail card — reverting
// to the default blue only once the user backs out to the list.
function isSelectedZip(zip) {
  return Boolean(selected && data.clients.find(client => client.client_id === selected)?.zip === zip);
}
function markerStyle(zip, hovering) {
  const active = hovering || isSelectedZip(zip);
  return {radius:active?11:7, weight:active?3:2, fillOpacity:active?1:.88, fillColor:active?'#e11d48':'#0284c7'};
}
function highlightZip(zip,on) {
  const marker = clientMarkers.get(zip); if (!marker) return;
  marker.setStyle(markerStyle(zip,on));
}

function syncMarkerSelection() {
  if (!mapView) return;
  clientMarkers.forEach((marker,zip) => marker.setStyle(markerStyle(zip,false)));
}

function renderEdChart(edData) {
  const canvas = $('#ed-chart');
  if (!canvas || typeof Chart === 'undefined') return;
  if (edChart) edChart.destroy();
  const points = edData.filter(item => item.edVisits > 0).map(item => ({x:item.maxTemp,y:item.edVisits}));
  edChart = new Chart(canvas,{type:'scatter',data:{datasets:[{data:points,backgroundColor:points.map(point=>point.x>=95?'rgba(225,29,72,.58)':'rgba(2,132,199,.28)'),pointRadius:3,pointHoverRadius:6}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:context=>`${context.raw.y} ED visits at ${context.raw.x}°F`}}},scales:{x:{title:{display:true,text:'Max daily temperature (°F)'},grid:{color:'#f1f5f9'},min:60,max:110},y:{title:{display:true,text:'Heat-related ED visits'},grid:{color:'#f1f5f9'},min:0}}}});
}

function populateTeams() {
  const select = $('#team-filter');
  select.innerHTML = '<option value="all">All teams</option>' + Object.keys(data.teams).sort().map(id => `<option value="${esc(id)}">${esc(id)} · ${data.teams[id]}</option>`).join('');
  select.value = team;
}

function route() {
  const workspace = location.hash === '#workspace';
  $('#home').hidden = workspace;
  $('#workspace').hidden = !workspace;
  document.body.dataset.route = workspace ? 'workspace' : 'home';
  window.scrollTo({top:0,behavior:'instant'});
  if (workspace) initMap().then(()=>setTimeout(()=>mapView?.invalidateSize(),0)).catch(error=>{console.error(error);toast('Map context could not be loaded. The call workflow is still available.');});
}

$('#close-info').onclick = () => $('#info').close();
window.onhashchange = route;
$$('[data-view]').forEach(button => button.onclick = () => { view = button.dataset.view; selected = null; render(); });
$('#team-filter').onchange = event => { team = event.target.value; selected = null; render(); };
$('#event-toggle').onclick = () => { eventVisible = !eventVisible; render(); };
$('#reset').onclick = () => { if (confirm('Reset all browser-local claims, outcomes, tasks, and AI drafts?')) { workflow={schemaVersion:1,clients:{}}; data.clients.forEach(client=>stateFor(client.client_id)); persist(); selected=null; view='list'; render(); toast('Demo workflow reset.'); } };
$('#guide-button').onclick = () => modal('Your check-in guide',`<p><b>1. Review the engine priority.</b> Band, reasons, uncertainty, and data quality come from the transparent Python scorecard.</p><p><b>2. Claim and prepare.</b> Generate an AI call brief grounded in the scored record. AI drafts language; it does not rank clients or make clinical decisions.</p><p><b>3. Record and follow through.</b> Confirm permission, save the outcome, assign tasks, and keep each request open until evidence supports “Support verified.”</p><p class="tiny">All people and locations are synthetic. Browser-local workflow state does not write to an EHR or re-score the engine.</p>`);
$('#sources').onclick = () => modal('Data & provenance',`<p><b>Rule engine:</b> 17 transparent factors scored in Python. Default weights are not calibrated for clinical use.</p><p><b>AI call brief:</b> POST <code>/api/callcard/&lt;client_id&gt;</code> sends the score context to Claude when configured; deterministic template mode is the fallback.</p><p><b>Synthetic clients and events:</b> No real patient data. Approximate ZIP markers are shown only because the fixture is synthetic.</p><p><b>Public context:</b> NYC Heat Vulnerability Index, NTA geography, and citywide heat-related ED observations. HVI is not an individual diagnosis.</p><p><b>Storage:</b> Claims, outcomes, tasks, and generated drafts are stored in this browser only. They do not update the server score snapshot.</p>`);
$$('[data-open-sources]').forEach(button => button.onclick = () => $('#sources').click());

try {
  const response = await fetch('/api/scores');
  if (!response.ok) throw new Error('Failed to load engine scores');
  data = await response.json();
  loadWorkflow(); populateTeams(); render(); route();
  const urgent = data.clients.filter(client=>client.band==='urgent').length;
  $('#preview-count').textContent = `${urgent} urgent · ${data.clients.length} scored`;
} catch (error) {
  $('#work').innerHTML = '<p class="empty">Could not load engine scores. Start the server with <code>python app/server.py</code> and reload.</p>';
  console.error(error);
}
