/**
 * EPPCOM RAG Chat-Widget
 * Eigenstaendiges Chat-Bubble-Widget — ruft direkt die RAG-API auf.
 *
 * Einbindung auf der Homepage:
 *   <script src="https://appdb.eppcom.de/widget/chat-widget.js"
 *           data-tenant="a0000000-0000-0000-0000-000000000001"
 *           data-api-key="c9c2f723d67806e57d5a058f8320aac6491295a4cfbfa716247cfc70d9e739de"
 *           data-api-url="https://appdb.eppcom.de/api/public/chat"
 *           data-accent="#2563EB"
 *           data-welcome="Hallo! Wie kann ich Ihnen helfen?"
 *           defer></script>
 */
(function () {
  "use strict";

  // ── Konfiguration aus Script-Tag lesen ──────────────────────────────────
  var script = document.currentScript || document.querySelector("script[data-tenant]");
  var API_URL = (script && script.getAttribute("data-api-url")) || "https://appdb.eppcom.de/api/public/chat";
  var TENANT  = (script && script.getAttribute("data-tenant"))  || "";
  var API_KEY = (script && script.getAttribute("data-api-key")) || "";
  var ACCENT  = (script && script.getAttribute("data-accent"))  || "#2563EB";
  var WELCOME = (script && script.getAttribute("data-welcome")) || "Hallo! Wie kann ich Ihnen helfen?";

  var SESSION = "web_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
  var isOpen  = false;
  var isLoading = false;

  // ── CSS injizieren ──────────────────────────────────────────────────────
  var style = document.createElement("style");
  style.textContent = "\n\
#eppcom-chat-bubble{position:fixed;bottom:24px;right:24px;z-index:99999;width:60px;height:60px;border-radius:50%;background:BG;color:#fff;border:none;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.25);display:flex;align-items:center;justify-content:center;transition:transform .2s}#eppcom-chat-bubble:hover{transform:scale(1.08)}#eppcom-chat-bubble svg{width:28px;height:28px;fill:#fff}\n\
#eppcom-chat-window{position:fixed;bottom:96px;right:24px;z-index:99999;width:380px;max-width:calc(100vw - 32px);height:520px;max-height:calc(100vh - 120px);background:#fff;border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,.18);display:none;flex-direction:column;overflow:hidden;font-family:Inter,system-ui,sans-serif}\n\
#eppcom-chat-window.open{display:flex}\n\
.eppcom-header{background:BG;color:#fff;padding:16px 20px;display:flex;align-items:center;gap:12px;min-height:56px}\n\
.eppcom-header-icon{width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,.15);display:flex;align-items:center;justify-content:center;font-size:18px}\n\
.eppcom-header-text{flex:1;font-size:15px;font-weight:600}\n\
.eppcom-header-sub{font-size:11px;font-weight:400;opacity:.8}\n\
.eppcom-close{background:none;border:none;color:#fff;font-size:22px;cursor:pointer;padding:4px 8px;opacity:.8;line-height:1}.eppcom-close:hover{opacity:1}\n\
.eppcom-msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}\n\
.eppcom-msg{max-width:85%;padding:10px 14px;border-radius:12px;font-size:14px;line-height:1.5;word-break:break-word;white-space:pre-wrap}\n\
.eppcom-msg-bot{background:#f1f5f9;color:#1e293b;align-self:flex-start;border-bottom-left-radius:4px}\n\
.eppcom-msg-user{background:BG;color:#fff;align-self:flex-end;border-bottom-right-radius:4px}\n\
.eppcom-msg-error{background:#fef2f2;color:#991b1b;align-self:flex-start;border-bottom-left-radius:4px;font-size:13px}\n\
.eppcom-typing{display:flex;gap:4px;padding:10px 14px;align-self:flex-start}.eppcom-typing span{width:8px;height:8px;background:#94a3b8;border-radius:50%;animation:eppcom-bounce .6s infinite alternate}.eppcom-typing span:nth-child(2){animation-delay:.2s}.eppcom-typing span:nth-child(3){animation-delay:.4s}\n\
@keyframes eppcom-bounce{to{opacity:.3;transform:translateY(-4px)}}\n\
.eppcom-input-row{display:flex;border-top:1px solid #e2e8f0;padding:12px;gap:8px;background:#fff}\n\
.eppcom-input{flex:1;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;font-size:14px;font-family:inherit;resize:none;outline:none;max-height:80px}.eppcom-input:focus{border-color:BG}\n\
.eppcom-send{background:BG;color:#fff;border:none;border-radius:8px;padding:0 14px;cursor:pointer;font-size:16px;display:flex;align-items:center}.eppcom-send:disabled{opacity:.5;cursor:not-allowed}\n\
.eppcom-powered{text-align:center;padding:4px 0 8px;font-size:10px;color:#94a3b8}\n\
".replace(/BG/g, ACCENT);
  document.head.appendChild(style);

  // ── HTML aufbauen ───────────────────────────────────────────────────────
  // Bubble Button
  var bubble = document.createElement("button");
  bubble.id = "eppcom-chat-bubble";
  bubble.innerHTML = '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.2L4 17.2V4h16v12z"/></svg>';
  bubble.onclick = toggleChat;
  document.body.appendChild(bubble);

  // Chat Window
  var win = document.createElement("div");
  win.id = "eppcom-chat-window";
  win.innerHTML = '\
<div class="eppcom-header">\
  <div class="eppcom-header-icon">&#129302;</div>\
  <div><div class="eppcom-header-text">EPPCOM Assistent</div><div class="eppcom-header-sub">KI-Chatbot &mdash; DSGVO-konform</div></div>\
  <button class="eppcom-close" onclick="document.getElementById(\'eppcom-chat-window\').classList.remove(\'open\');document.getElementById(\'eppcom-chat-bubble\').style.display=\'flex\'">&times;</button>\
</div>\
<div class="eppcom-msgs" id="eppcom-msgs"></div>\
<div class="eppcom-input-row">\
  <textarea class="eppcom-input" id="eppcom-input" rows="1" placeholder="Ihre Frage eingeben..."></textarea>\
  <button class="eppcom-send" id="eppcom-send">&#10148;</button>\
</div>\
<div class="eppcom-powered">EPPCOM Solutions &mdash; KI-Automatisierung</div>';
  document.body.appendChild(win);

  // ── Event Listeners ─────────────────────────────────────────────────────
  var inputEl = document.getElementById("eppcom-input");
  var sendBtn = document.getElementById("eppcom-send");

  sendBtn.onclick = sendMessage;
  inputEl.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  inputEl.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 80) + "px";
  });

  // ── Funktionen ──────────────────────────────────────────────────────────
  function toggleChat() {
    isOpen = !isOpen;
    win.classList.toggle("open", isOpen);
    bubble.style.display = isOpen ? "none" : "flex";
    if (isOpen && !document.getElementById("eppcom-msgs").hasChildNodes()) {
      addMsg("bot", WELCOME);
    }
    if (isOpen) inputEl.focus();
  }

  function addMsg(role, text) {
    var msgs = document.getElementById("eppcom-msgs");
    var div = document.createElement("div");
    div.className = "eppcom-msg eppcom-msg-" + role;
    div.textContent = text;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  }

  function showTyping() {
    var msgs = document.getElementById("eppcom-msgs");
    var div = document.createElement("div");
    div.className = "eppcom-typing";
    div.id = "eppcom-typing";
    div.innerHTML = "<span></span><span></span><span></span>";
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function removeTyping() {
    var el = document.getElementById("eppcom-typing");
    if (el) el.remove();
  }

  function sendMessage() {
    var text = inputEl.value.trim();
    if (!text || isLoading) return;

    addMsg("user", text);
    inputEl.value = "";
    inputEl.style.height = "auto";
    sendBtn.disabled = true;
    isLoading = true;
    showTyping();

    fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Tenant-ID": TENANT,
        "X-API-Key": API_KEY
      },
      body: JSON.stringify({ query: text, session_id: SESSION })
    })
    .then(function (res) {
      if (!res.ok) throw new Error("Status " + res.status);
      return res.json();
    })
    .then(function (data) {
      removeTyping();
      addMsg("bot", data.answer || "Keine Antwort erhalten.");
    })
    .catch(function (err) {
      removeTyping();
      addMsg("error", "Fehler: " + err.message + ". Bitte versuchen Sie es erneut.");
    })
    .finally(function () {
      sendBtn.disabled = false;
      isLoading = false;
      inputEl.focus();
    });
  }
})();
