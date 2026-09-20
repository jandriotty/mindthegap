const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

let data = null;
let selected = null;
let filter = 'all';
let callcards = {};

const bandLabels = {urgent:'Urgent',high:'High',moderate:'Moderate',low:'Low',monitor:'Monitor'};
const bandOrder = ['urgent','high','moderate','low','monitor'];

function toast(s) {
  const t = $('#toast');
  t.textContent = s;
  t.classList.add('show');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), 4500);
}

function modal(title, body) {
  $('#info-title').textContent = title;
  $('#info-body').innerHTML = body;
  $('#info').showModal();
}

async function loadScores() {
  const res = await fetch('/api/scores');
  if (!res.ok) throw new Error('Failed to load scores');
  data = await res.json();
  render();
}

function render() {
  if (!data) return;
  const focus = data.clients[0]?.hazard_focus;
  const active = focus && focus.phase !== 'none';

  $('#event').innerHTML = active
    ? `<div class="event"><span><b>&#9679; ${esc(focus.product || 'Heat hazard active')}</b> &middot; ${esc(focus.note)}</span><span>Engine as-of: ${esc(data.asof)}</span></div>`
    : `<div class="event inactive"><span><b>No active hazard</b> &middot; All clients in monitor mode</span><span>Engine as-of: ${esc(data.asof)}</span></div>`;

  $('#ws-eyebrow').textContent = `TEAM WORKSPACE · ${Object.keys(data.teams).length} TEAMS · ${data.clients.length} CLIENTS`;

  document.querySelectorAll('[data-view]').forEach(b => {
    b.classList.toggle('active', (selected ? 'detail' : 'list') === b.dataset.view);
  });

  if (selected) renderCard();
  else renderList();
}

function renderList() {
  const all = data.clients;
  const counts = {};
  for (const b of bandOrder) counts[b] = 0;
  for (const c of all) counts[c.band] = (counts[c.band] || 0) + 1;

  const filtered = filter === 'all' ? all : all.filter(c => c.band === filter);

  $('#work').innerHTML = `
    <div class="work-head">
      <span class="eyebrow">SCORED BY RULE ENGINE</span>
      <h2>Who needs a check-in?</h2>
      <p>${all.length} clients scored with ${data.clients[0]?.factors?.length || 17} factors. Open a person to see why they were flagged and generate a call card.</p>
    </div>
    <div class="queue-overview">
      <div class="queue-metric urgent"><b>${counts.urgent || 0}</b><span>Urgent</span></div>
      <div class="queue-metric high"><b>${counts.high || 0}</b><span>High</span></div>
      <div class="queue-metric moderate"><b>${counts.moderate || 0}</b><span>Moderate</span></div>
      <div class="queue-metric low"><b>${(counts.low || 0) + (counts.monitor || 0)}</b><span>Low / Monitor</span></div>
    </div>
    <div class="tabs">
      <button data-filter="all" class="${filter === 'all' ? 'active' : ''}">All &middot; ${all.length}</button>
      ${bandOrder.filter(b => counts[b]).map(b =>
        `<button data-filter="${b}" class="${filter === b ? 'active' : ''}">${bandLabels[b]} &middot; ${counts[b]}</button>`
      ).join('')}
    </div>
    ${filtered.length ? filtered.map(c => `
      <button class="client" data-client="${c.client_id}">
        <div class="client-top">
          <strong>${esc(c.client_id)} &#8599;</strong>
          <div>
            <span class="band ${c.band}">${bandLabels[c.band] || c.band}</span>
            <span class="confidence-tag ${c.confidence_label.toLowerCase()}-conf">${esc(c.confidence_label)} conf.</span>
          </div>
        </div>
        <p>${esc(c.reasons.slice(0, 2).map(r => r.text).join(' · ')) || 'No active risk factors'}</p>
        <small>
          ${esc(c.program_type)} · Age ${c.age} · ${esc(c.borough)} ${c.zip}
          · Priority ${c.priority.expected.toFixed(1)} (${c.band_range})
          · Reach: ${esc(c.reach.label)}
          · Rank #${c.rank} on ${esc(c.team_id)}${c.in_top_k ? ' *' : ''}
        </small>
      </button>
    `).join('') : '<div class="empty">No clients in this band.</div>'}
    <div class="data-note">
      <b>Default weights, NOT calibrated.</b> All data is synthetic.
      Scores use a hand-specified additive points scorecard &mdash; not ML.
      Confidence is reported separately from risk.
      ${data.clients.some(c => c.in_top_k) ? ' Clients marked * are in the top-K for their team.' : ''}
    </div>`;

  document.querySelectorAll('[data-filter]').forEach(b =>
    b.onclick = () => { filter = b.dataset.filter; render(); });
  document.querySelectorAll('[data-client]').forEach(b =>
    b.onclick = () => { selected = b.dataset.client; render(); });
}

function renderCard() {
  const c = data.clients.find(x => x.client_id === selected);
  if (!c) { selected = null; render(); return; }

  const unknownFactors = c.factors.filter(f => f.state === 'unknown' || f.state === 'unknown_stale');
  const presentFactors = c.factors.filter(f => f.state === 'present' && f.counted);

  const card = callcards[c.client_id];

  $('#work').innerHTML = `
    <div class="card">
      <button class="back" id="back">&larr; Back to call list</button>
      <div class="card-title">
        <h2>${esc(c.client_id)}</h2>
        <div>
          <span class="band ${c.band}">${bandLabels[c.band]}</span>
          <span class="confidence-tag ${c.confidence_label.toLowerCase()}-conf">${esc(c.confidence_label)} confidence</span>
          <span class="pill">Synthetic</span>
        </div>
      </div>

      <div class="reason-box">
        <h3>Why this priority?</h3>
        <p><strong>HAZARD</strong>${esc(c.hazard_focus.note)}
          ${c.hazard_focus.product ? ` (${esc(c.hazard_focus.product)})` : ''}
          · Multiplier: ${c.hazard_multiplier}x</p>
        <p><strong>WHY THIS PERSON</strong>${c.reasons.length
          ? c.reasons.map(r => esc(r.text)).join('. ') + '.'
          : 'No active risk factors identified.'}</p>
        <p><strong>PRIORITY RANGE</strong>
          ${c.priority.low.toFixed(1)} &ndash; ${c.priority.expected.toFixed(1)} &ndash; ${c.priority.high.toFixed(1)}
          (band: ${esc(c.band_range)})
          · Vulnerability: ${c.vulnerability.expected.toFixed(1)} of ${c.factors.reduce((s,f) => s + f.points_full, 0).toFixed(1)} possible</p>
        <p><strong>STILL UNCERTAIN</strong>${c.unknowns_to_ask.length
          ? c.unknowns_to_ask.map(u => `${esc(u.question)} (swing: ${u.swing_points} pts${u.stale ? '; stale' : ''}${u.restricted ? '; restricted' : ''})`).join('. ')
          : 'No high-impact unknowns.'}</p>
        <p><strong>CONFIDENCE</strong>
          ${esc(c.confidence_label)} (${(c.overall_confidence * 100).toFixed(0)}%)
          · Data: ${(c.data_confidence * 100).toFixed(0)}%
          ${c.hazard_focus.trust ? ` · Hazard trust: ${(c.hazard_focus.trust * 100).toFixed(0)}%` : ''}</p>
        ${c.visibility.length ? `<p><strong>BLIND SPOTS</strong>${c.visibility.map(v => esc(v)).join('. ')}.</p>` : ''}
        ${c.check_in ? `<p><strong>CHECK-IN RECOMMENDED</strong>${c.check_in_reasons.map(r => esc(r)).join('; ')}.</p>` : ''}
        <details><summary>Reach &amp; contact details</summary>
          <p>Reach: ${esc(c.reach.label)} (${(c.reach.score * 100).toFixed(0)}%) &mdash; ${esc(c.reach.route)}</p>
          ${c.contact ? `<p>Phone: ${esc(c.contact.phone_status)}
            ${c.contact.verified_date ? ` · Verified: ${esc(c.contact.verified_date)}` : ''}
            ${c.contact.alternate ? ` · Alternate: ${esc(c.contact.alternate)}` : ''}
            ${c.contact.preferred_method ? ` · Preferred: ${esc(c.contact.preferred_method)}` : ''}</p>` : ''}
        </details>
      </div>

      <div class="factgrid">
        <div class="fact ${c.cooling_status ? (c.cooling_status === 'working_ac' ? '' : 'present') : 'unknown'}">
          Cooling: <b>${esc(c.cooling_status || 'unknown')}</b>
          <small>${c.cooling_asof ? `As of ${esc(c.cooling_asof)}` : 'Not recorded'}</small>
        </div>
        <div class="fact">
          Housing: <b>${esc(c.housing_type || 'unknown')}</b>
          <small>${esc(c.borough)} ${c.zip}</small>
        </div>
        <div class="fact">
          Medications: <b>${c.medications === null ? 'unavailable' : c.medications.length === 0 ? 'confirmed none' : esc(c.medications.join(', '))}</b>
        </div>
        <div class="fact">
          HIE consent: <b>${esc(c.hie_consent)}</b>
          <small>Age ${c.age} · ${esc(c.program_type)}</small>
        </div>
      </div>

      <h3 class="section-title">Factor breakdown</h3>
      <table class="factor-table">
        <thead><tr><th>Factor</th><th>Tier</th><th>State</th><th>Points</th><th>Detail</th></tr></thead>
        <tbody>
          ${c.factors
            .sort((a, b) => a.tier - b.tier || b.expected - a.expected)
            .map(f => `<tr class="${f.counted ? 'counted' : ''} ${f.state.startsWith('unknown') ? 'unknown-row' : ''}">
              <td>${esc(f.label)}${f.group ? ` <span class="tiny">(${esc(f.group)})</span>` : ''}</td>
              <td>${f.tier}</td>
              <td><span class="state ${f.state}">${esc(f.state)}${f.proxy ? ' proxy' : ''}${f.restricted ? ' restricted' : ''}</span></td>
              <td>${f.expected.toFixed(1)}${f.counted ? ' *' : ''}</td>
              <td>${esc(f.detail)}</td>
            </tr>`).join('')}
        </tbody>
      </table>
      <p class="tiny">* = counted toward vulnerability score (highest in its group). Unknown factors show their expected (prior-weighted) points.</p>

      <h3 class="section-title">Call card</h3>
      <div id="callcard-area">
        ${card ? renderCallCard(card) : `
          <p class="tiny">Generate a personalized call script using the engine's scoring data.</p>
          <button class="primary generate-btn" id="gen-card">Generate call card</button>
        `}
      </div>
    </div>`;

  $('#back').onclick = () => { selected = null; filter = 'all'; render(); };

  const genBtn = $('#gen-card');
  if (genBtn) {
    genBtn.onclick = async () => {
      genBtn.disabled = true;
      genBtn.textContent = 'Generating...';
      try {
        const res = await fetch(`/api/callcard/${c.client_id}`, { method: 'POST' });
        if (!res.ok) throw new Error('Generation failed');
        const card = await res.json();
        callcards[c.client_id] = card;
        render();
        toast('Call card generated.');
      } catch (e) {
        toast('Could not generate call card. Check that the server has an API key (or template mode will be used).');
        genBtn.disabled = false;
        genBtn.textContent = 'Retry';
      }
    };
  }
}

function renderCallCard(card) {
  return `
    <div class="callcard-box">
      <h3>Greeting</h3>
      <div class="callcard-greeting">${esc(card.greeting)}</div>

      <h3>Check-in questions</h3>
      ${card.questions.map((q, i) => `
        <div class="callcard-question">
          <p><b>${i + 1}.</b> ${esc(q.question)}</p>
          <p class="why">${esc(q.why_asking)}</p>
          ${q.follow_up_if_yes ? `<p class="followup">If yes: ${esc(q.follow_up_if_yes)}</p>` : ''}
          ${q.follow_up_if_no ? `<p class="followup">If no: ${esc(q.follow_up_if_no)}</p>` : ''}
        </div>
      `).join('')}

      <h3>Closing</h3>
      <div class="callcard-closing">${esc(card.closing)}</div>

      <p class="tiny" style="margin-top:12px">
        ${card.reasons?.length ? `Why flagged: ${card.reasons.join('; ')}` : ''}
        ${card.unknowns?.length ? ` · Key unknowns: ${card.unknowns.join('; ')}` : ''}
      </p>
    </div>`;
}

// --- routing and init ---
function route() {
  const work = location.hash === '#workspace';
  $('#home').hidden = work;
  $('#workspace').hidden = !work;
  document.body.dataset.route = work ? 'workspace' : 'home';
  window.scrollTo({ top: 0, behavior: 'instant' });
}

$('#close-info').onclick = () => $('#info').close();
window.onhashchange = route;

document.querySelectorAll('[data-view]').forEach(b =>
  b.onclick = () => {
    if (b.dataset.view === 'list') { selected = null; render(); }
  });

$('#guide-button').onclick = () => modal('Your check-in guide',
  `<p><b>1. Understand the priority.</b> Open a client to see the full factor breakdown &mdash; every factor, its evidence, its state, and its contribution to the score.</p>
   <p><b>2. Generate a call card.</b> The call card uses the engine's unknowns and risk factors to create personalized questions. Template mode works without an API key; LLM mode generates richer, context-aware scripts.</p>
   <p><b>3. Follow through.</b> After the call, record what you learned. Each confirmed answer sharpens the next event's priority list.</p>
   <p class="tiny">Scores use a hand-specified additive points scorecard (not ML). Default weights are NOT calibrated &mdash; tune with clinicians before any real use.</p>`);

$('#sources').onclick = () => modal('Data &amp; provenance',
  `<p><b>Rule engine:</b> 17 factors scored with a log-odds additive scorecard. Weights are from published heat-health studies (Bouchama 2007, Semenza 1996) where available; remaining weights are assumed defaults. See docs/rule-engine.md.</p>
   <p><b>Synthetic clients:</b> 10 hand-crafted records designed to test engine edge cases (psychotic-spectrum diagnosis, medication proxies, thin files, stale data, restricted records, cross-facility ED patterns). No real patient data.</p>
   <p><b>Synthetic heat events:</b> A 7-day NYC heat wave (Jul 20&ndash;26, 2026) with hourly truth, NWS-style alerts, and forecast error models. Peak: Manhattan heat index 107&deg;F on Thursday Jul 23.</p>
   <p><b>HVI reference:</b> NYC Heat Vulnerability Index by ZIP (subset of 10 ZCTAs from NYC Open Data).</p>
   <p><b>Call cards:</b> Generated per-client using the engine's factor results. LLM mode sends the scoring context to Claude; template mode uses deterministic rules. No real calls are placed.</p>
   <p><b>Storage:</b> Call cards are cached in browser memory only. The server computes scores on startup. No EHR or external system connections.</p>`);

document.querySelectorAll('[data-open-sources]').forEach(b => b.onclick = () => $('#sources').click());

$('#team-filter').onclick = () => {
  if (!data) return;
  const teams = Object.keys(data.teams).sort();
  const items = ['All teams', ...teams];
  const current = $('#team-filter').textContent;
  const next = items[(items.indexOf(current) + 1) % items.length];
  $('#team-filter').textContent = next;
  if (next === 'All teams') {
    loadScores();
  } else {
    fetch(`/api/scores?team=${encodeURIComponent(next)}`)
      .then(r => r.json())
      .then(d => { data = d; render(); });
  }
};

route();
loadScores().catch(e => {
  $('#work').innerHTML = '<p class="empty">Could not load engine scores. Make sure the server is running: <code>python app/server.py</code></p>';
  console.error(e);
});
