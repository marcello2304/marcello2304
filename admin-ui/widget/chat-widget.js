/**
 * EPPCOM RAG Chat-Widget
 * Floating Chat-Bubble — ruft /api/public/widget-chat auf (Domain-Whitelist, kein API-Key).
 *
 * Einbindung:
 *   <script src="https://appdb.eppcom.de/widget/chat-widget.js"
 *           data-api-url="https://appdb.eppcom.de/api/public/widget-chat"
 *           data-accent="#2563EB"
 *           data-welcome="Hallo! Willkommen bei EPPCOM Solutions — Ihrem Partner für KI-Automatisierung.\nIch bin Ihr digitaler Assistent und helfe Ihnen gerne weiter."
 *           defer></script>
 */
(function () {
  "use strict";

  var script = document.currentScript || document.querySelector("script[data-api-url]");
  var API_URL = (script && script.getAttribute("data-api-url")) || "https://appdb.eppcom.de/api/public/widget-chat";
  var ACCENT  = (script && script.getAttribute("data-accent"))  || "#2563EB";
  var WELCOME = (script && script.getAttribute("data-welcome")) || "Hallo! Willkommen bei EPPCOM Solutions \u2014 Ihrem Partner f\u00fcr KI-Automatisierung.\nIch bin Ihr digitaler Assistent und helfe Ihnen gerne weiter.";

  var SESSION = "web_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
  var isOpen  = false;
  var isLoading = false;

  // ── Typebot-nahes CSS ───────────────────────────────────────────────────
  var css = [
    /* Bubble */
    "#eppcom-cb{position:fixed;bottom:24px;right:24px;z-index:99999;width:56px;height:56px;border-radius:50%;background:VAR;color:#fff;border:none;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.2);display:flex;align-items:center;justify-content:center;transition:transform .15s ease}",
    "#eppcom-cb:hover{transform:scale(1.08)}",
    "#eppcom-cb svg{width:26px;height:26px;fill:currentColor}",
    /* Preview message */
    "#eppcom-preview{position:fixed;bottom:90px;right:24px;z-index:99998;background:#fff;border-radius:12px;padding:12px 16px;box-shadow:0 2px 12px rgba(0,0,0,.12);font:14px/1.5 Inter,system-ui,sans-serif;color:#1e293b;max-width:260px;cursor:pointer;display:none}",
    "#eppcom-preview.show{display:block}",
    "#eppcom-preview-close{position:absolute;top:2px;right:6px;background:none;border:none;font-size:16px;cursor:pointer;color:#94a3b8;line-height:1}",
    /* Window – Typebot-ähnlich */
    "#eppcom-win{position:fixed;bottom:96px;right:24px;z-index:99999;width:400px;max-width:calc(100vw - 32px);height:560px;max-height:calc(100vh - 120px);background:#fff;border-radius:16px;box-shadow:0 8px 30px rgba(0,0,0,.16);display:none;flex-direction:column;overflow:hidden;font-family:Inter,system-ui,-apple-system,sans-serif}",
    "#eppcom-win.open{display:flex}",
    /* Header */
    ".ec-hdr{background:VAR;color:#fff;padding:14px 16px;display:flex;align-items:center;gap:10px}",
    ".ec-hdr-av{width:40px;height:40px;border-radius:50%;background:rgba(255,255,255,.18);display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0}",
    ".ec-hdr-txt{flex:1}",
    ".ec-hdr-name{font-size:15px;font-weight:600}",
    ".ec-hdr-sub{font-size:11px;opacity:.75;margin-top:1px}",
    ".ec-hdr-x{background:none;border:none;color:#fff;font-size:20px;cursor:pointer;padding:4px 6px;opacity:.7;line-height:1;flex-shrink:0}",
    ".ec-hdr-x:hover{opacity:1}",
    /* Messages area */
    ".ec-msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;background:#ffffff}",
    /* Bot message – Typebot style: hostBubble */
    ".ec-msg{max-width:82%;font-size:14px;line-height:1.55;word-break:break-word}",
    ".ec-bot{align-self:flex-start;display:flex;gap:8px;align-items:flex-end}",
    ".ec-bot-av{width:28px;height:28px;border-radius:50%;background:VAR;display:flex;align-items:center;justify-content:center;font-size:13px;color:#fff;flex-shrink:0}",
    ".ec-bot-bubble{background:#F0F4FF;color:#1E293B;padding:10px 14px;border-radius:6px 12px 12px 6px;white-space:pre-wrap}",
    /* User message – Typebot style: guestBubble */
    ".ec-user{align-self:flex-end}",
    ".ec-user-bubble{background:VAR;color:#fff;padding:10px 14px;border-radius:12px 6px 6px 12px;white-space:pre-wrap}",
    /* Error */
    ".ec-err{align-self:flex-start;display:flex;gap:8px;align-items:flex-end}",
    ".ec-err .ec-bot-bubble{background:#fef2f2;color:#991b1b}",
    /* Typing */
    ".ec-typing{display:flex;gap:5px;padding:10px 14px;background:#F0F4FF;border-radius:6px 12px 12px 6px;align-self:flex-start;margin-left:36px}",
    ".ec-typing span{width:7px;height:7px;background:#94a3b8;border-radius:50%;animation:ecb .6s infinite alternate}",
    ".ec-typing span:nth-child(2){animation-delay:.15s}",
    ".ec-typing span:nth-child(3){animation-delay:.3s}",
    "@keyframes ecb{to{opacity:.3;transform:translateY(-3px)}}",
    /* Input */
    ".ec-input-row{display:flex;border-top:1px solid #e2e8f0;padding:10px 12px;gap:8px;background:#fff}",
    ".ec-inp{flex:1;border:1px solid #e2e8f0;border-radius:10px;padding:10px 12px;font-size:14px;font-family:inherit;resize:none;outline:none;max-height:80px;background:#fff;color:#1E293B}",
    ".ec-inp::placeholder{color:#9CA3AF}",
    ".ec-inp:focus{border-color:VAR;box-shadow:0 0 0 1px VAR}",
    ".ec-send{background:VAR;color:#fff;border:none;border-radius:10px;padding:0 14px;cursor:pointer;font-size:18px;display:flex;align-items:center;transition:opacity .15s}",
    ".ec-send:disabled{opacity:.4;cursor:not-allowed}",
    ".ec-foot{text-align:center;padding:4px 0 8px;font-size:10px;color:#94a3b8;background:#fff}",
    "@media(max-width:440px){#eppcom-win{right:8px;left:8px;width:auto;bottom:80px;height:calc(100vh - 100px);max-height:none;border-radius:12px}#eppcom-cb{bottom:16px;right:16px}}"
  ].join("\n").replace(/VAR/g, ACCENT);

  var styleEl = document.createElement("style");
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  // ── Bubble ──────────────────────────────────────────────────────────────
  var bubble = document.createElement("button");
  bubble.id = "eppcom-cb";
  bubble.setAttribute("aria-label", "Chat öffnen");
  bubble.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 3C6.5 3 2 6.58 2 11a7.23 7.23 0 002.75 5.5L3 21l4.5-2.5A11.27 11.27 0 0012 19c5.5 0 10-3.58 10-8s-4.5-8-10-8z"/></svg>';
  bubble.onclick = toggleChat;
  document.body.appendChild(bubble);

  // ── Preview Message ─────────────────────────────────────────────────────
  var preview = document.createElement("div");
  preview.id = "eppcom-preview";
  preview.innerHTML = 'Hallo! Kann ich Ihnen helfen?<button id="eppcom-preview-close">&times;</button>';
  preview.onclick = function (e) { if (e.target.id !== "eppcom-preview-close") { toggleChat(); } else { preview.classList.remove("show"); } };
  document.body.appendChild(preview);
  setTimeout(function () { if (!isOpen) preview.classList.add("show"); }, 5000);

  // ── Chat Window ─────────────────────────────────────────────────────────
  var win = document.createElement("div");
  win.id = "eppcom-win";
  win.innerHTML =
    '<div class="ec-hdr">' +
      '<div class="ec-hdr-av">\uD83E\uDD16</div>' +
      '<div class="ec-hdr-txt"><div class="ec-hdr-name">EPPCOM Assistent</div><div class="ec-hdr-sub">KI-Chatbot \u2014 DSGVO-konform</div></div>' +
      '<button class="ec-hdr-x" id="eppcom-close">\u00D7</button>' +
    '</div>' +
    '<div class="ec-msgs" id="ec-msgs"></div>' +
    '<div class="ec-input-row">' +
      '<textarea class="ec-inp" id="ec-inp" rows="1" placeholder="Ihre Frage eingeben..."></textarea>' +
      '<button class="ec-send" id="ec-send">\u27A4</button>' +
    '</div>' +
    '<div class="ec-foot">EPPCOM Solutions \u2014 KI-Automatisierung</div>';
  document.body.appendChild(win);

  // ── Events ──────────────────────────────────────────────────────────────
  document.getElementById("ec-send").onclick = sendMessage;
  document.getElementById("eppcom-close").onclick = function () { isOpen = false; win.classList.remove("open"); bubble.style.display = "flex"; };
  document.getElementById("ec-inp").addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  document.getElementById("ec-inp").addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 80) + "px";
  });

  // ── Functions ───────────────────────────────────────────────────────────
  function toggleChat() {
    isOpen = !isOpen;
    win.classList.toggle("open", isOpen);
    bubble.style.display = isOpen ? "none" : "flex";
    preview.classList.remove("show");
    if (isOpen && !document.getElementById("ec-msgs").hasChildNodes()) {
      addBot(WELCOME);
    }
    if (isOpen) document.getElementById("ec-inp").focus();
  }

  function addBot(text) {
    var msgs = document.getElementById("ec-msgs");
    var wrap = document.createElement("div");
    wrap.className = "ec-msg ec-bot";
    wrap.innerHTML = '<div class="ec-bot-av">\uD83E\uDD16</div><div class="ec-bot-bubble"></div>';
    wrap.querySelector(".ec-bot-bubble").textContent = text;
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function addUser(text) {
    var msgs = document.getElementById("ec-msgs");
    var wrap = document.createElement("div");
    wrap.className = "ec-msg ec-user";
    wrap.innerHTML = '<div class="ec-user-bubble"></div>';
    wrap.querySelector(".ec-user-bubble").textContent = text;
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function addError(text) {
    var msgs = document.getElementById("ec-msgs");
    var wrap = document.createElement("div");
    wrap.className = "ec-msg ec-err";
    wrap.innerHTML = '<div class="ec-bot-av">\u26A0\uFE0F</div><div class="ec-bot-bubble"></div>';
    wrap.querySelector(".ec-bot-bubble").textContent = text;
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function showTyping() {
    var msgs = document.getElementById("ec-msgs");
    var div = document.createElement("div");
    div.className = "ec-typing";
    div.id = "ec-typing";
    div.innerHTML = "<span></span><span></span><span></span>";
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function removeTyping() {
    var el = document.getElementById("ec-typing");
    if (el) el.remove();
  }

  function sendMessage() {
    var inp = document.getElementById("ec-inp");
    var text = inp.value.trim();
    if (!text || isLoading) return;

    addUser(text);
    inp.value = "";
    inp.style.height = "auto";
    document.getElementById("ec-send").disabled = true;
    isLoading = true;
    showTyping();

    fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: text, session_id: SESSION })
    })
    .then(function (res) {
      if (!res.ok) return res.text().then(function (t) { throw new Error(t || "Status " + res.status); });
      return res.json();
    })
    .then(function (data) {
      removeTyping();
      addBot(data.answer || "Keine Antwort erhalten.");
    })
    .catch(function (err) {
      removeTyping();
      addError("Es gab einen Fehler. Bitte versuchen Sie es erneut.");
    })
    .finally(function () {
      document.getElementById("ec-send").disabled = false;
      isLoading = false;
      document.getElementById("ec-inp").focus();
    });
  }
})();
