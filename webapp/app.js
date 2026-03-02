// RAG Test Webapp — app.js
// Hetzner Self-Hosted RAG Platform

// ── Konfiguration aus LocalStorage laden ────────────────────────────────
const cfg = {
  get webhookUrl()  { return document.getElementById('webhookUrl').value.trim(); },
  get tenantSlug()  { return document.getElementById('tenantSlug').value.trim() || 'demo'; },
  get model()       { return document.getElementById('model').value; },
  get topK()        { return parseInt(document.getElementById('topK').value); },
  get minSim()      { return parseInt(document.getElementById('minSim').value) / 100; },
  get directMode()  { return document.getElementById('directMode').checked; },
  get pgApiUrl()    { return document.getElementById('pgApiUrl').value.trim(); },
};

// ── LocalStorage Persistenz ──────────────────────────────────────────────
const STORAGE_KEY = 'rag-test-config';

function saveConfig() {
  const data = {
    webhookUrl: document.getElementById('webhookUrl').value,
    tenantSlug: document.getElementById('tenantSlug').value,
    model:      document.getElementById('model').value,
    topK:       document.getElementById('topK').value,
    minSim:     document.getElementById('minSim').value,
    directMode: document.getElementById('directMode').checked,
    pgApiUrl:   document.getElementById('pgApiUrl').value,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

function loadConfig() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (!saved) return;
  try {
    const data = JSON.parse(saved);
    for (const [key, value] of Object.entries(data)) {
      const el = document.getElementById(key);
      if (!el) continue;
      if (el.type === 'checkbox') el.checked = value;
      else el.value = value;
    }
  } catch(e) {}
  updateSliderLabels();
}

// ── Slider Labels ────────────────────────────────────────────────────────
function updateSliderLabels() {
  document.getElementById('topKVal').textContent = document.getElementById('topK').value;
  document.getElementById('minSimVal').textContent =
    (parseInt(document.getElementById('minSim').value) / 100).toFixed(2);
}

document.getElementById('topK').addEventListener('input', () => { updateSliderLabels(); saveConfig(); });
document.getElementById('minSim').addEventListener('input', () => { updateSliderLabels(); saveConfig(); });
['webhookUrl','tenantSlug','model','directMode','pgApiUrl'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('change', saveConfig);
});

// ── Enter-Handling im Textarea ───────────────────────────────────────────
document.getElementById('queryInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendQuery();
  }
});

// Auto-resize Textarea
document.getElementById('queryInput').addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

// ── Status Indicator ─────────────────────────────────────────────────────
function setStatus(state, text) {
  const el = document.getElementById('statusIndicator');
  const dot = el.querySelector('.dot');
  dot.className = 'dot dot-' + state;
  el.querySelector('span:last-child')?.remove();
  const span = document.createElement('span');
  span.textContent = text;
  el.appendChild(span);
}

// ── Chat-Nachricht einfügen ──────────────────────────────────────────────
function addMessage(role, content, extras = {}) {
  const chatBody = document.getElementById('chatBody');
  const div = document.createElement('div');
  div.className = 'msg msg-' + (role === 'user' ? 'user' : role === 'error' ? 'error' : 'bot');

  const time = new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  const avatar = role === 'user' ? '👤' : (role === 'error' ? '⚠️' : '🤖');

  div.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-content">
      <div class="msg-bubble">${formatContent(content)}</div>
      <div class="msg-time">${time}${extras.latency ? ` · ${extras.latency}ms` : ''}</div>
    </div>
  `;

  chatBody.appendChild(div);
  chatBody.scrollTop = chatBody.scrollHeight;
  return div;
}

function formatContent(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

// ── Typing Indicator ─────────────────────────────────────────────────────
function showTyping() {
  const chatBody = document.getElementById('chatBody');
  const div = document.createElement('div');
  div.className = 'msg msg-bot';
  div.id = 'typing-indicator';
  div.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div class="msg-content">
      <div class="msg-bubble">
        <div class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>`;
  chatBody.appendChild(div);
  chatBody.scrollTop = chatBody.scrollHeight;
}

function removeTyping() {
  document.getElementById('typing-indicator')?.remove();
}

// ── Quellen-Panel aktualisieren ──────────────────────────────────────────
function updateSources(sources, latencyData) {
  const body = document.getElementById('sourcesBody');
  body.innerHTML = '';

  if (!sources || sources.length === 0) {
    body.innerHTML = '<div class="sources-empty">Keine Quellen gefunden.<br>Versuche eine andere Frage oder senke die Ähnlichkeitsschwelle.</div>';
    return;
  }

  sources.forEach((src, i) => {
    const card = document.createElement('div');
    card.className = 'source-card';
    const simPct = src.similarity ? Math.round(src.similarity * 100) : '?';
    const simColor = simPct >= 80 ? '#22c55e' : simPct >= 60 ? '#eab308' : '#94a3b8';

    card.innerHTML = `
      <div class="source-rank">#${i + 1} Quelle</div>
      <div class="source-title">${escHtml(src.document_title || 'Unbekannt')}</div>
      <div class="source-meta">
        ${src.doc_type ? `<span class="source-badge">${escHtml(src.doc_type)}</span>` : ''}
        ${src.section ? `<span class="source-badge">${escHtml(src.section)}</span>` : ''}
        ${src.page_number ? `<span class="source-badge">S. ${src.page_number}</span>` : ''}
      </div>
      <div class="source-sim" style="color:${simColor}">Ähnlichkeit: ${simPct}%</div>
      ${src.content ? `<div class="source-excerpt">${escHtml(src.content)}</div>` : ''}
    `;
    body.appendChild(card);
  });

  if (latencyData) {
    const bar = document.createElement('div');
    bar.className = 'latency-bar';
    bar.innerHTML = `
      <div class="l-row"><span>Gesamt</span><span class="latency-val">${latencyData.total ?? '?'}ms</span></div>
      ${latencyData.embed ? `<div class="l-row"><span>Embedding</span><span class="latency-val">${latencyData.embed}ms</span></div>` : ''}
      ${latencyData.search ? `<div class="l-row"><span>Vektorsuche</span><span class="latency-val">${latencyData.search}ms</span></div>` : ''}
      ${latencyData.llm ? `<div class="l-row"><span>LLM</span><span class="latency-val">${latencyData.llm}ms</span></div>` : ''}
      <div class="l-row"><span>Chunks gefunden</span><span class="latency-val">${sources.length}</span></div>
    `;
    body.appendChild(bar);
  }
}

function escHtml(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Anfrage senden ───────────────────────────────────────────────────────
async function sendQuery() {
  const input = document.getElementById('queryInput');
  const query = input.value.trim();
  if (!query) return;

  const btn = document.getElementById('sendBtn');
  btn.disabled = true;
  input.value = '';
  input.style.height = 'auto';

  addMessage('user', query);
  showTyping();
  setStatus('yellow', 'Verarbeite...');

  const startTime = Date.now();

  try {
    let result;

    if (cfg.directMode && cfg.pgApiUrl) {
      result = await queryDirect(query);
    } else {
      result = await queryViaWebhook(query);
    }

    removeTyping();

    const totalLatency = Date.now() - startTime;
    addMessage('bot', result.answer || 'Keine Antwort erhalten.', { latency: totalLatency });

    updateSources(result.sources || [], {
      total: result.latency_ms || totalLatency,
      embed: result.embed_ms,
      search: result.search_ms,
      llm: result.llm_ms,
    });

    setStatus('green', 'Verbunden');

  } catch (err) {
    removeTyping();
    const msg = err.message || 'Unbekannter Fehler';
    addMessage('error', `**Fehler:** ${msg}\n\n_Prüfe ob n8n läuft und die Webhook-URL korrekt ist._`);
    updateSources([], null);
    setStatus('red', 'Fehler');
    console.error('RAG Query Error:', err);
  }

  btn.disabled = false;
  input.focus();
}

// ── n8n Webhook Query ────────────────────────────────────────────────────
async function queryViaWebhook(query) {
  const url = cfg.webhookUrl;
  if (!url) throw new Error('Webhook-URL nicht konfiguriert. Trage sie in der Sidebar ein.');

  const body = {
    tenant_slug: cfg.tenantSlug,
    query,
    session_id: getSessionId(),
    top_k: cfg.topK,
    min_similarity: cfg.minSim,
    model: cfg.model,
  };

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
  }

  return await res.json();
}

// ── Direkt-Query (PostgreSQL REST API) ──────────────────────────────────
async function queryDirect(query) {
  // Für direkten Postgres-Zugriff ohne n8n:
  // Setzt einen kleinen Proxy-Server voraus (serve-webapp.sh startet diesen)
  const url = cfg.pgApiUrl;
  if (!url) throw new Error('Postgres API URL nicht konfiguriert.');

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tenant_slug: cfg.tenantSlug,
      query,
      top_k: cfg.topK,
      min_similarity: cfg.minSim,
    }),
  });

  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

// ── Quick Questions ──────────────────────────────────────────────────────
function askQuestion(btn) {
  document.getElementById('queryInput').value = btn.textContent;
  sendQuery();
}

// ── Session ID ───────────────────────────────────────────────────────────
function getSessionId() {
  let id = sessionStorage.getItem('rag-session-id');
  if (!id) {
    id = 'webapp-' + Math.random().toString(36).slice(2, 10);
    sessionStorage.setItem('rag-session-id', id);
  }
  return id;
}

// ── Chat leeren ──────────────────────────────────────────────────────────
function clearChat() {
  const body = document.getElementById('chatBody');
  body.innerHTML = '';
  document.getElementById('sourcesBody').innerHTML =
    '<div class="sources-empty">Chat wurde geleert.</div>';
  sessionStorage.removeItem('rag-session-id');
  setStatus('gray', 'Nicht verbunden');
}

// ── DB-Statistiken ───────────────────────────────────────────────────────
async function showStats() {
  document.getElementById('statsModal').classList.add('open');
  const body = document.getElementById('statsBody');
  body.innerHTML = 'Lade Statistiken...';

  // Versuche Stats über einen einfachen Ping-Endpoint zu laden
  try {
    const url = cfg.webhookUrl.replace('/webhook/rag-query', '/webhook/stats')
                              .replace('/rag-query', '/stats');
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tenant_slug: cfg.tenantSlug }),
    });

    if (res.ok) {
      const data = await res.json();
      body.innerHTML = `
        <table>
          <thead><tr><th>Metrik</th><th>Wert</th></tr></thead>
          <tbody>
            <tr><td>Tenant</td><td>${escHtml(cfg.tenantSlug)}</td></tr>
            <tr><td>Quellen</td><td>${data.source_count ?? '?'}</td></tr>
            <tr><td>Dokumente</td><td>${data.doc_count ?? '?'}</td></tr>
            <tr><td>Chunks</td><td>${data.chunk_count ?? '?'}</td></tr>
            <tr><td>Embeddings</td><td>${data.embed_count ?? '?'}</td></tr>
            <tr><td>Konversationen</td><td>${data.conv_count ?? '?'}</td></tr>
          </tbody>
        </table>`;
    } else {
      throw new Error('Stats-Endpoint nicht verfügbar');
    }
  } catch(e) {
    body.innerHTML = `
      <p style="color:#94a3b8; margin-bottom:16px">Stats-Endpoint nicht erreichbar.</p>
      <p style="font-size:12px; color:#64748b">
        Führe in der Datenbank aus:<br><br>
        <code style="background:#1a1d27; padding:8px; border-radius:6px; display:block; margin-top:8px">
          SELECT * FROM public.get_tenant_stats('${escHtml(cfg.tenantSlug)}');
        </code>
      </p>`;
  }
}

function closeStats() {
  document.getElementById('statsModal').classList.remove('open');
}

// ── Init ────────────────────────────────────────────────────────────────
loadConfig();
updateSliderLabels();

// Versuche gespeicherte URL zu prüfen
if (cfg.webhookUrl) {
  setStatus('gray', 'URL konfiguriert — sende erste Anfrage');
} else {
  setStatus('gray', 'Webhook-URL eintragen');
}

// CORS-Hinweis wenn lokale Datei
if (location.protocol === 'file:') {
  console.warn('⚠ Webapp als file:// geöffnet. CORS-Fehler möglich. Besser: bash scripts/serve-webapp.sh');
}
