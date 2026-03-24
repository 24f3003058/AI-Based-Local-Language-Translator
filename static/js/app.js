/* ── AI Local Language Translator — Frontend App ── */
'use strict';

// ── State ────────────────────────────────────────────────────────────────────
const state = {
  languages: [],
  domains: ['casual', 'medical', 'legal', 'technical', 'religious'],
  sourceLang: 'en',
  targetLang: 'hi',
  domain: 'casual',
  sessionEnabled: false,
  sessionId: null,
  history: [],       // [{source, target, sl, tl, domain}]
  glossary: [],
  batchSegments: [], // [{id, source_text, status, translated_text}]
  translating: false,
};

// ── Language metadata ─────────────────────────────────────────────────────────
const LANG_FLAGS = {
  hi:'🇮🇳', mr:'🇮🇳', ta:'🇮🇳', bn:'🇧🇩', te:'🇮🇳',
  gu:'🇮🇳', kn:'🇮🇳', ml:'🇮🇳', pa:'🇮🇳', or:'🇮🇳', en:'🇬🇧',
};
const DOMAIN_ICONS = {
  casual:'💬', medical:'🏥', legal:'⚖️', technical:'⚙️', religious:'🛕',
};

// ── Utilities ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const qs = sel => document.querySelector(sel);

function toast(msg, type = 'info') {
  const c = $('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'}</span> ${msg}`;
  c.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function langClass(code) { return `lang-${code}`; }

function applyLangFont(el, code) {
  el.className = el.className.replace(/lang-\w+/g, '').trim();
  if (code && code !== 'auto') el.classList.add(`lang-${code}`);
}

function langName(code) {
  const l = state.languages.find(x => x.code === code);
  return l ? l.name : code?.toUpperCase() || '?';
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
  return json;
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  const data = await api('/api/languages');
  state.languages = data.languages;
  state.domains   = data.domains;
  populateLangSelects();
  populateDomainSelects();
  setupEventListeners();
  updateStatusDot(true);
  loadGlossary();
  loadSessions();
}

function updateStatusDot(online) {
  const dot = qs('.api-status .dot');
  const txt = qs('.api-status .status-text');
  if (online) {
    dot.classList.remove('offline');
    txt.textContent = 'API Ready';
  } else {
    dot.classList.add('offline');
    txt.textContent = 'API Error';
  }
}

function populateLangSelects() {
  ['source-lang', 'target-lang', 'batch-target-lang',
   'g-source-lang', 'g-target-lang',
   'modal-source-lang', 'modal-target-lang'].forEach(id => {
    const el = $(id);
    if (!el) return;
    const isSource = id.includes('source');
    el.innerHTML = '';
    if (id === 'source-lang') {
      const opt = new Option('Auto Detect', 'auto');
      el.appendChild(opt);
    }
    state.languages.forEach(l => {
      const opt = new Option(`${LANG_FLAGS[l.code] || ''} ${l.name} (${l.code})`, l.code);
      el.appendChild(opt);
    });
    if (id === 'source-lang') el.value = 'auto';
    else if (id === 'target-lang') el.value = state.targetLang;
  });
}

function populateDomainSelects() {
  ['domain-select', 'batch-domain', 'g-domain', 'modal-domain'].forEach(id => {
    const el = $(id);
    if (!el) return;
    el.innerHTML = '';
    state.domains.forEach(d => {
      el.appendChild(new Option(`${DOMAIN_ICONS[d]} ${d.charAt(0).toUpperCase()+d.slice(1)}`, d));
    });
  });
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function setupEventListeners() {
  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b === btn));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === `tab-${tab}`));
    });
  });

  // Source textarea
  $('source-text').addEventListener('input', () => {
    $('char-count').textContent = $('source-text').value.length + ' chars';
  });

  // Language selects
  $('source-lang').addEventListener('change', e => {
    state.sourceLang = e.target.value;
    updateSourceLangLabel();
  });
  $('target-lang').addEventListener('change', e => {
    state.targetLang = e.target.value;
    updateTargetLangLabel();
    applyLangFont($('output-text'), state.targetLang);
  });
  $('domain-select').addEventListener('change', e => { state.domain = e.target.value; });

  // Swap button
  $('swap-btn').addEventListener('click', swapLangs);

  // Detect button
  $('detect-btn').addEventListener('click', detectLang);

  // Translate button
  $('translate-btn').addEventListener('click', doTranslate);

  // Keyboard shortcut Ctrl+Enter
  $('source-text').addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') doTranslate();
  });

  // Copy button
  $('copy-btn').addEventListener('click', () => {
    const txt = $('output-text').innerText;
    if (!txt || txt === state._placeholder) return;
    navigator.clipboard.writeText(txt).then(() => {
      $('copy-btn').textContent = '✓ Copied';
      $('copy-btn').classList.add('copied');
      setTimeout(() => { $('copy-btn').textContent = '⎘ Copy'; $('copy-btn').classList.remove('copied'); }, 2000);
    });
  });

  // Session toggle
  $('session-toggle').addEventListener('change', e => {
    state.sessionEnabled = e.target.checked;
    if (state.sessionEnabled && !state.sessionId) createSession();
    else if (!state.sessionEnabled) {
      state.sessionId = null;
      $('session-badge').textContent = '';
      $('session-badge').classList.remove('visible');
    }
  });

  // Batch upload
  const dropzone = $('batch-dropzone');
  const fileInput = $('batch-file');
  dropzone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => handleFileUpload(fileInput.files[0]));
  dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', e => {
    e.preventDefault(); dropzone.classList.remove('dragover');
    handleFileUpload(e.dataTransfer.files[0]);
  });
  $('translate-batch-btn').addEventListener('click', translateBatch);

  // Glossary
  $('add-glossary-btn').addEventListener('click', () => openModal('glossary-modal'));
  $('glossary-modal-form').addEventListener('submit', addGlossaryEntry);
  $('g-domain').addEventListener('change', loadGlossary);
  $('g-source-lang').addEventListener('change', loadGlossary);

  // Modal close
  document.querySelectorAll('[data-close-modal]').forEach(el => {
    el.addEventListener('click', e => {
      e.target.closest('.modal-overlay').classList.remove('open');
    });
  });

  // New session btn
  $('new-session-btn').addEventListener('click', loadSessions);
}

// ── Language helpers ──────────────────────────────────────────────────────────
function updateSourceLangLabel() {
  const code = $('source-lang').value;
  $('source-lang-label').innerHTML = code === 'auto'
    ? `🔍 Auto Detect`
    : `${LANG_FLAGS[code] || ''} ${langName(code)}`;
  applyLangFont($('source-text'), code === 'auto' ? null : code);
}

function updateTargetLangLabel() {
  const code = $('target-lang').value;
  $('target-lang-label').innerHTML = `${LANG_FLAGS[code] || ''} ${langName(code)}`;
}

function swapLangs() {
  const sl = $('source-lang');
  const tl = $('target-lang');
  const srcVal = sl.value === 'auto' ? state.sourceLang : sl.value;
  // Set source to current target (if supported)
  const srcOpts = [...sl.options].map(o => o.value);
  if (srcOpts.includes(tl.value)) sl.value = tl.value;
  // Set target to what was source
  tl.value = srcVal;
  state.sourceLang = sl.value;
  state.targetLang = tl.value;
  updateSourceLangLabel();
  updateTargetLangLabel();

  // Swap text
  const srcText = $('source-text').value;
  const tgtText = $('output-text').innerText;
  if (tgtText && tgtText !== state._placeholder) {
    $('source-text').value = tgtText;
    setOutput(srcText, tl.value);
  }
  applyLangFont($('output-text'), state.targetLang);
}

// ── Detect language ───────────────────────────────────────────────────────────
async function detectLang() {
  const text = $('source-text').value.trim();
  if (!text) { toast('Enter some text to detect language', 'error'); return; }
  try {
    const r = await api('/api/detect', { method: 'POST', body: { text } });
    if (r.supported) {
      $('source-lang').value = r.detected_lang;
      state.sourceLang = r.detected_lang;
      updateSourceLangLabel();
      toast(`Detected: ${langName(r.detected_lang)} (${Math.round(r.confidence * 100)}% confidence)`, 'success');
    } else {
      toast(`Language not supported: ${r.detected_lang || 'unknown'}`, 'error');
    }
  } catch (e) { toast(e.message, 'error'); }
}

// ── Translate ─────────────────────────────────────────────────────────────────
async function doTranslate() {
  const text = $('source-text').value.trim();
  if (!text) { toast('Enter text to translate', 'error'); return; }
  if (state.translating) return;

  state.translating = true;
  $('translate-btn').disabled = true;
  showLoading();

  try {
    const body = {
      text,
      source_lang: $('source-lang').value,
      target_lang: $('target-lang').value,
      domain: $('domain-select').value,
      session_id: state.sessionEnabled ? state.sessionId : null,
    };
    const r = await api('/api/translate', { method: 'POST', body });

    setOutput(r.translated_text, r.target_lang);
    applyLangFont($('output-text'), r.target_lang);

    // Update token count
    $('token-count').textContent = `${r.tokens_used} tokens`;

    // Glossary chips
    showGlossaryChips(r.glossary_applied, text);

    // Add to history
    state.history.unshift({ source: text, target: r.translated_text, sl: r.source_lang, tl: r.target_lang, domain: r.domain });
    renderHistory();

    // Update detected lang if auto
    if ($('source-lang').value === 'auto' && r.source_lang) {
      $('source-lang-label').innerHTML = `${LANG_FLAGS[r.source_lang] || ''} ${langName(r.source_lang)} (detected)`;
    }
  } catch (e) {
    showError(e.message);
  } finally {
    state.translating = false;
    $('translate-btn').disabled = false;
  }
}

state._placeholder = 'Translation will appear here…';

function showLoading() {
  const el = $('output-text');
  el.className = 'output-text loading';
  el.innerHTML = '<div class="spinner"></div> Translating…';
  $('glossary-chips').innerHTML = '';
}

function showError(msg) {
  const el = $('output-text');
  el.className = 'output-text';
  el.innerHTML = `<span style="color:var(--danger)">⚠ ${msg}</span>`;
}

function setOutput(text, langCode) {
  const el = $('output-text');
  el.className = 'output-text';
  el.textContent = text;
  applyLangFont(el, langCode);
}

function showGlossaryChips(count, _text) {
  const c = $('glossary-chips');
  c.innerHTML = '';
  if (count > 0) {
    const chip = document.createElement('span');
    chip.className = 'glossary-chip';
    chip.textContent = `📖 ${count} glossary term${count > 1 ? 's' : ''} applied`;
    c.appendChild(chip);
  }
}

// ── History ───────────────────────────────────────────────────────────────────
function renderHistory() {
  const list = $('history-list');
  if (state.history.length === 0) {
    list.innerHTML = '<p class="history-empty">Translations appear here</p>';
    return;
  }
  list.innerHTML = state.history.slice(0, 20).map((h, i) => `
    <div class="history-item" onclick="restoreHistory(${i})">
      <div class="h-source">${LANG_FLAGS[h.sl]||''} ${esc(h.source.slice(0,60))}${h.source.length>60?'…':''}</div>
      <div class="h-target lang-${h.tl}">${LANG_FLAGS[h.tl]||''} ${esc(h.target.slice(0,60))}${h.target.length>60?'…':''}</div>
    </div>
  `).join('');
}

function restoreHistory(i) {
  const h = state.history[i];
  $('source-text').value = h.source;
  setOutput(h.target, h.tl);
  $('source-lang').value = h.sl;
  $('target-lang').value = h.tl;
  $('domain-select').value = h.domain;
  state.sourceLang = h.sl; state.targetLang = h.tl; state.domain = h.domain;
  updateSourceLangLabel(); updateTargetLangLabel();
  applyLangFont($('output-text'), h.tl);
}

// ── Session ───────────────────────────────────────────────────────────────────
async function createSession() {
  try {
    const r = await api('/api/sessions', {
      method: 'POST',
      body: {
        source_lang: $('source-lang').value,
        target_lang: $('target-lang').value,
        domain: $('domain-select').value,
      },
    });
    state.sessionId = r.session_id;
    $('session-badge').textContent = `Session: ${r.session_id}`;
    $('session-badge').classList.add('visible');
    toast(`Session started: ${r.session_id}`, 'success');
  } catch (e) { toast('Failed to create session: ' + e.message, 'error'); }
}

// ── Batch ─────────────────────────────────────────────────────────────────────
function handleFileUpload(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const text = e.target.result;
    if (file.name.endsWith('.csv')) parseCsv(text);
    else parseTxt(text);
    $('batch-dropzone').style.display = 'none';
    $('batch-controls').style.display = 'flex';
    $('batch-table-section').style.display = 'block';
    renderBatchTable();
  };
  reader.readAsText(file, 'UTF-8');
}

function parseCsv(text) {
  const lines = text.trim().split('\n');
  const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
  const idIdx = headers.indexOf('id'), textIdx = headers.indexOf('source_text');
  if (textIdx === -1) { toast('CSV must have a "source_text" column', 'error'); return; }
  state.batchSegments = lines.slice(1).map((line, i) => {
    const cols = parseCSVLine(line);
    return { id: idIdx >= 0 ? cols[idIdx] : String(i+1), source_text: cols[textIdx] || '', status: 'pending', translated_text: '' };
  }).filter(s => s.source_text);
}

function parseCSVLine(line) {
  const result = []; let current = ''; let inQuotes = false;
  for (let c of line) {
    if (c === '"') inQuotes = !inQuotes;
    else if (c === ',' && !inQuotes) { result.push(current.trim()); current = ''; }
    else current += c;
  }
  result.push(current.trim());
  return result;
}

function parseTxt(text) {
  state.batchSegments = text.split('\n')
    .map((l, i) => ({ id: String(i+1), source_text: l.trim(), status: 'pending', translated_text: '' }))
    .filter(s => s.source_text);
}

function renderBatchTable() {
  const tbody = $('batch-tbody');
  const tl = $('batch-target-lang').value;
  tbody.innerHTML = state.batchSegments.map(s => `
    <tr>
      <td>${esc(s.id)}</td>
      <td>${esc(s.source_text)}</td>
      <td class="lang-${tl}">${esc(s.translated_text)}</td>
      <td><span class="status-pill ${s.status}">${s.status}</span></td>
    </tr>
  `).join('');
}

async function translateBatch() {
  const targetLang = $('batch-target-lang').value;
  const sourceLang = $('batch-source-lang').value;
  const domain     = $('batch-domain').value;

  if (!targetLang) { toast('Select target language', 'error'); return; }
  if (state.batchSegments.length === 0) { toast('Upload a file first', 'error'); return; }

  $('translate-batch-btn').disabled = true;
  $('batch-progress').style.display = 'block';

  const pending = state.batchSegments.filter(s => s.status === 'pending');
  let done = 0;

  try {
    const r = await api('/api/batch', {
      method: 'POST',
      body: { segments: pending, source_lang: sourceLang, target_lang: targetLang, domain },
    });
    r.results.forEach(res => {
      const seg = state.batchSegments.find(s => s.id === res.id);
      if (seg) {
        seg.translated_text = res.translated_text || '';
        seg.status = res.error ? 'error' : 'done';
      }
      done++;
    });
    $('batch-progress-bar').style.width = '100%';
    renderBatchTable();
    toast(`Translated ${done} segments`, 'success');
    $('export-batch-btn').style.display = 'inline-flex';
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    $('translate-batch-btn').disabled = false;
  }

  // Export button
  $('export-batch-btn').onclick = () => exportBatchCsv(targetLang);
}

function exportBatchCsv(targetLang) {
  const rows = [['id','source_text','translated_text','target_lang']];
  state.batchSegments.forEach(s => rows.push([s.id, s.source_text, s.translated_text, targetLang]));
  const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g,'""')}"`).join(',')).join('\n');
  const blob = new Blob(['\uFEFF'+csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'translations.csv';
  a.click(); URL.revokeObjectURL(url);
}

// ── Glossary ──────────────────────────────────────────────────────────────────
async function loadGlossary() {
  const domain     = ($('g-domain')?.value) || '';
  const sourceLang = ($('g-source-lang')?.value) || '';
  const params = new URLSearchParams();
  if (domain) params.set('domain', domain);
  if (sourceLang) params.set('source_lang', sourceLang);
  try {
    const r = await api(`/api/glossary?${params}`);
    state.glossary = r;
    renderGlossary();
  } catch (e) { console.error(e); }
}

function renderGlossary() {
  const tbody = $('glossary-tbody');
  if (state.glossary.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:24px">No entries found. Add your first term!</td></tr>';
    return;
  }
  tbody.innerHTML = state.glossary.map(e => `
    <tr>
      <td><span class="lang-${e.source_lang}">${esc(e.source_term)}</span></td>
      <td>${langName(e.source_lang)}</td>
      <td><span class="lang-${e.target_lang}">${esc(e.target_term)}</span></td>
      <td>${langName(e.target_lang)}</td>
      <td><span class="domain-badge ${e.domain}">${e.domain}</span></td>
      <td><span class="use-badge">${e.use_count}</span></td>
      <td>
        <button class="btn btn-danger btn-sm" onclick="deleteGlossaryEntry('${e.id}')">✕</button>
      </td>
    </tr>
  `).join('');
}

function openModal(id) {
  $(id).classList.add('open');
}

async function addGlossaryEntry(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = {
    source_lang:  fd.get('source_lang'),
    source_term:  fd.get('source_term'),
    target_lang:  fd.get('target_lang'),
    target_term:  fd.get('target_term'),
    domain:       fd.get('domain'),
    notes:        fd.get('notes'),
  };
  try {
    await api('/api/glossary', { method: 'POST', body });
    $('glossary-modal').classList.remove('open');
    e.target.reset();
    toast('Glossary entry added', 'success');
    loadGlossary();
  } catch (err) { toast(err.message, 'error'); }
}

async function deleteGlossaryEntry(id) {
  if (!confirm('Delete this glossary entry?')) return;
  try {
    await api(`/api/glossary/${id}`, { method: 'DELETE' });
    toast('Deleted', 'success');
    loadGlossary();
  } catch (e) { toast(e.message, 'error'); }
}

// ── Sessions panel ────────────────────────────────────────────────────────────
async function loadSessions() {
  try {
    const sessions = await api('/api/sessions');
    renderSessions(sessions);
  } catch (e) { console.error(e); }
}

function renderSessions(sessions) {
  const grid = $('sessions-grid');
  if (!sessions.length) {
    grid.innerHTML = '<p style="color:var(--muted);font-size:.875rem">No sessions yet. Enable Context in the Translate tab to start one.</p>';
    return;
  }
  grid.innerHTML = sessions.map(s => `
    <div class="session-card">
      <div class="s-id">${s.session_id}</div>
      <div class="s-langs">${LANG_FLAGS[s.source_lang]||'🔍'} ${langName(s.source_lang)} → ${LANG_FLAGS[s.target_lang]||''} ${langName(s.target_lang)}</div>
      <div class="s-meta">
        <span class="domain-badge ${s.domain}">${s.domain}</span>
        &nbsp;${s.history_length} exchange${s.history_length!==1?'s':''}
        ${s.has_summary ? '· summarized' : ''}
        <br><small>${new Date(s.created_at).toLocaleString()}</small>
      </div>
      <div class="s-actions">
        <button class="btn btn-outline btn-sm" onclick="resumeSession('${s.session_id}')">▶ Resume</button>
        <button class="btn btn-danger btn-sm" onclick="deleteSessionUI('${s.session_id}')">✕</button>
      </div>
    </div>
  `).join('');
}

function resumeSession(id) {
  state.sessionId = id;
  state.sessionEnabled = true;
  $('session-toggle').checked = true;
  $('session-badge').textContent = `Session: ${id}`;
  $('session-badge').classList.add('visible');
  // Switch to translate tab
  document.querySelector('[data-tab="translate"]').click();
  toast(`Resumed session ${id}`, 'success');
}

async function deleteSessionUI(id) {
  if (!confirm(`Delete session ${id}?`)) return;
  try {
    await api(`/api/sessions/${id}`, { method: 'DELETE' });
    if (state.sessionId === id) { state.sessionId = null; state.sessionEnabled = false; }
    toast('Session deleted', 'success');
    loadSessions();
  } catch (e) { toast(e.message, 'error'); }
}

// ── Escape HTML ───────────────────────────────────────────────────────────────
function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Kick off ──────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', init);
window.restoreHistory = restoreHistory;
window.deleteGlossaryEntry = deleteGlossaryEntry;
window.resumeSession = resumeSession;
window.deleteSessionUI = deleteSessionUI;
