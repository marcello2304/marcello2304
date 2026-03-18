/**
 * EPPCOM RAG Chat-Widget (Text + Voice) — Typebot-Style, Mobile-optimiert
 *
 * Einbindung auf der Homepage (vor </body>):
 *   <script src="https://appdb.eppcom.de/widget/chat-widget.js"
 *           data-api-url="https://appdb.eppcom.de/api/public/widget-chat"
 *           data-voice-token-url="https://appdb.eppcom.de/api/public/voice-token"
 *           data-livekit-url="wss://voice.eppcom.de"
 *           data-accent="#667eea"
 *           data-welcome="Hallo! Willkommen bei EPPCOM Solutions."
 *           data-auto-open="true"
 *           defer></script>
 */
(function () {
  "use strict";

  var script = document.currentScript || document.querySelector("script[data-api-url]");
  var API_URL = (script && script.getAttribute("data-api-url")) || "https://appdb.eppcom.de/api/public/widget-chat";
  var VOICE_TOKEN_URL = (script && script.getAttribute("data-voice-token-url")) || "https://appdb.eppcom.de/api/public/voice-token";
  var LIVEKIT_URL = (script && script.getAttribute("data-livekit-url")) || "wss://voice.eppcom.de";
  var ACCENT = (script && script.getAttribute("data-accent")) || "#667eea";
  var WELCOME = (script && script.getAttribute("data-welcome")) || "Hallo! Willkommen bei EPPCOM Solutions \u2014 Ihrem Partner f\u00fcr KI-Automatisierung.\nWie m\u00f6chten Sie kommunizieren?";
  var AUTO_OPEN = (script && script.getAttribute("data-auto-open")) !== "false";

  var SESSION = "web_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
  var isOpen = false;
  var isLoading = false;
  var mode = null;
  var voiceRoom = null;
  var voiceConnecting = false;
  var isMobile = /Android|iPhone|iPad|iPod|Opera Mini|IEMobile/i.test(navigator.userAgent) || window.innerWidth < 640;

  // ── CSS (Typebot-Style) ─────────────────────────────────────────────────
  var css = [
    /* Reset */
    "#typebot-bubble,#typebot-bubble *,#typebot-win,#typebot-win *,#typebot-preview{box-sizing:border-box;-webkit-tap-highlight-color:transparent}",

    /* ─── Bubble Button (Typebot-identisch) ─── */
    "#typebot-bubble{position:fixed;bottom:20px;right:20px;z-index:42424242;width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,VAR,#764ba2);color:#fff;border:none;cursor:pointer;box-shadow:0 4px 15px rgba(102,126,234,.45);display:flex;align-items:center;justify-content:center;transition:transform .2s cubic-bezier(.34,1.56,.64,1),box-shadow .2s;-webkit-appearance:none}",
    "#typebot-bubble:hover{transform:scale(1.1);box-shadow:0 6px 20px rgba(102,126,234,.55)}",
    "#typebot-bubble:active{transform:scale(.95)}",
    "#typebot-bubble svg{width:24px;height:24px;fill:#fff;transition:transform .2s}",

    /* ─── Preview Message (Typebot-Style) ─── */
    "#typebot-preview{position:fixed;bottom:78px;right:20px;z-index:42424241;background:#fff;border-radius:16px;padding:12px 36px 12px 16px;box-shadow:0 2px 15px rgba(0,0,0,.1);font:14px/1.5 'Open Sans',Inter,system-ui,sans-serif;color:#303235;max-width:256px;cursor:pointer;opacity:0;transform:translateY(10px);transition:opacity .3s,transform .3s;pointer-events:none}",
    "#typebot-preview.show{opacity:1;transform:translateY(0);pointer-events:auto}",
    "#typebot-preview-close{position:absolute;top:4px;right:8px;background:none;border:none;font-size:18px;cursor:pointer;color:#aaa;line-height:1;padding:4px}",
    "#typebot-preview-close:hover{color:#666}",

    /* ─── Chat Window (Typebot-Style) ─── */
    "#typebot-win{position:fixed;bottom:80px;right:20px;z-index:42424242;width:400px;height:600px;background:#fff;border-radius:24px;box-shadow:0 5px 40px rgba(0,0,0,.16);display:none;flex-direction:column;overflow:hidden;font-family:'Open Sans',Inter,system-ui,-apple-system,sans-serif;opacity:0;transform:scale(.95) translateY(20px);transition:opacity .25s ease,transform .25s cubic-bezier(.34,1.56,.64,1)}",
    "#typebot-win.open{display:flex}",
    "#typebot-win.visible{opacity:1;transform:scale(1) translateY(0)}",

    /* Mobile: Vollbild */
    "@media(max-width:640px){" +
      "#typebot-win{top:0;left:0;right:0;bottom:0;width:100%;height:100%;max-width:none;max-height:none;border-radius:0;box-shadow:none}" +
      "#typebot-bubble{bottom:16px;right:16px}" +
      "#typebot-preview{bottom:74px;right:16px;max-width:200px}" +
      ".tb-mode-select{padding:12px!important}" +
      ".tb-msgs{padding:12px!important}" +
      ".tb-voice-area{padding:20px 16px!important}" +
    "}",

    /* Safe area (Notch/Dynamic Island) */
    "@supports(padding-top:env(safe-area-inset-top)){" +
      "@media(max-width:640px){" +
        ".tb-hdr{padding-top:calc(14px + env(safe-area-inset-top))}" +
        ".tb-foot{padding-bottom:calc(6px + env(safe-area-inset-bottom))}" +
        ".tb-input-row{padding-bottom:calc(8px + env(safe-area-inset-bottom))}" +
      "}" +
    "}",

    /* ─── Header (Typebot-Style) ─── */
    ".tb-hdr{background:linear-gradient(135deg,VAR,#764ba2);color:#fff;padding:14px 16px;display:flex;align-items:center;gap:10px;flex-shrink:0}",
    ".tb-hdr-av{width:40px;height:40px;border-radius:50%;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}",
    ".tb-hdr-txt{flex:1;min-width:0}",
    ".tb-hdr-name{font-size:16px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".tb-hdr-sub{font-size:12px;opacity:.8;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".tb-hdr-x,.tb-hdr-back{background:none;border:none;color:#fff;font-size:22px;cursor:pointer;padding:6px 8px;opacity:.7;line-height:1;flex-shrink:0;-webkit-appearance:none;transition:opacity .15s}",
    ".tb-hdr-x:hover,.tb-hdr-back:hover,.tb-hdr-x:active,.tb-hdr-back:active{opacity:1}",
    ".tb-hdr-back{display:none;font-size:20px}",
    ".tb-hdr-back.show{display:block}",

    /* ─── Messages (Typebot hostBubble/guestBubble) ─── */
    ".tb-msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px;background:#fff;-webkit-overflow-scrolling:touch}",
    ".tb-msg{max-width:80%;font-size:15px;line-height:1.55;word-break:break-word;animation:tb-fade .3s ease}",
    "@keyframes tb-fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}",

    /* Bot message — Typebot hostBubble */
    ".tb-bot{align-self:flex-start;display:flex;gap:8px;align-items:flex-end}",
    ".tb-bot-av{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,VAR,#764ba2);display:flex;align-items:center;justify-content:center;font-size:14px;color:#fff;flex-shrink:0}",
    ".tb-bot-bubble{background:#F7F8FF;color:#303235;padding:12px 16px;border-radius:6px 20px 20px 6px;white-space:pre-wrap;box-shadow:0 1px 4px rgba(0,0,0,.04)}",

    /* User message — Typebot guestBubble */
    ".tb-user{align-self:flex-end}",
    ".tb-user-bubble{background:linear-gradient(135deg,VAR,#764ba2);color:#fff;padding:12px 16px;border-radius:20px 6px 6px 20px;white-space:pre-wrap;box-shadow:0 1px 4px rgba(102,126,234,.2)}",

    /* Error */
    ".tb-err{align-self:flex-start;display:flex;gap:8px;align-items:flex-end}",
    ".tb-err .tb-bot-bubble{background:#fef2f2;color:#991b1b}",

    /* Typing (Typebot-Style dots) */
    ".tb-typing{display:flex;gap:5px;padding:12px 16px;background:#F7F8FF;border-radius:6px 20px 20px 6px;align-self:flex-start;margin-left:40px;box-shadow:0 1px 4px rgba(0,0,0,.04)}",
    ".tb-typing span{width:7px;height:7px;background:#b0b3b8;border-radius:50%;animation:tb-dot .6s infinite alternate}",
    ".tb-typing span:nth-child(2){animation-delay:.15s}",
    ".tb-typing span:nth-child(3){animation-delay:.3s}",
    "@keyframes tb-dot{to{opacity:.3;transform:translateY(-3px)}}",

    /* ─── Input (Typebot-Style) ─── */
    ".tb-input-row{display:flex;border-top:1px solid #f0f0f0;padding:10px 12px;gap:8px;background:#fff;flex-shrink:0}",
    ".tb-inp{flex:1;border:1px solid #e5e7eb;border-radius:20px;padding:10px 16px;font-size:16px;font-family:inherit;resize:none;outline:none;max-height:80px;background:#fff;color:#303235;-webkit-appearance:none;transition:border-color .15s}",
    ".tb-inp::placeholder{color:#9CA3AF}",
    ".tb-inp:focus{border-color:VAR;box-shadow:0 0 0 1px VAR}",
    ".tb-send{background:linear-gradient(135deg,VAR,#764ba2);color:#fff;border:none;border-radius:50%;width:40px;height:40px;min-width:40px;cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center;transition:opacity .15s,transform .15s;-webkit-appearance:none}",
    ".tb-send:hover{transform:scale(1.05)}",
    ".tb-send:active{transform:scale(.95)}",
    ".tb-send:disabled{opacity:.4;cursor:not-allowed;transform:none}",
    ".tb-foot{text-align:center;padding:6px 0 8px;font-size:10px;color:#b0b3b8;background:#fff;flex-shrink:0}",

    /* ─── Mode Selection (Typebot Button-Input Style) ─── */
    ".tb-mode-select{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px;background:#fff;-webkit-overflow-scrolling:touch}",
    ".tb-choice-row{display:flex;flex-wrap:wrap;gap:8px;margin-left:40px;animation:tb-fade .3s ease}",
    ".tb-choice-btn{padding:10px 18px;border-radius:20px;border:1px solid VAR;background:#fff;color:VAR;cursor:pointer;font-size:14px;font-weight:500;font-family:inherit;transition:all .15s ease;-webkit-appearance:none;white-space:nowrap}",
    ".tb-choice-btn:hover{background:VAR;color:#fff;transform:translateY(-1px);box-shadow:0 2px 8px rgba(102,126,234,.25)}",
    ".tb-choice-btn:active{transform:scale(.96);box-shadow:none}",

    /* ─── Voice UI ─── */
    ".tb-voice-area{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;padding:24px}",
    ".tb-voice-btn{width:80px;height:80px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s ease;font-size:32px;-webkit-appearance:none}",
    ".tb-voice-btn:active{transform:scale(.92)}",
    ".tb-voice-btn.idle{background:#f3f4f6;color:#6b7280}",
    ".tb-voice-btn.connecting{background:#fbbf24;color:#fff;animation:tb-pulse 1.5s infinite}",
    ".tb-voice-btn.active{background:#ef4444;color:#fff;animation:tb-pulse 1.5s infinite}",
    "@keyframes tb-pulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.4)}50%{box-shadow:0 0 0 14px rgba(239,68,68,0)}}",
    ".tb-voice-status{font-size:14px;color:#6b7280;text-align:center;padding:0 8px}",
    ".tb-voice-status.connected{color:#059669;font-weight:500}",
    "#tb-voice-audio{display:none}"
  ].join("\n").replace(/VAR/g, ACCENT);

  var styleEl = document.createElement("style");
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  // Viewport meta (mobile zoom fix)
  if (!document.querySelector('meta[name="viewport"]')) {
    var meta = document.createElement("meta");
    meta.name = "viewport";
    meta.content = "width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no";
    document.head.appendChild(meta);
  }

  // ── Bubble ──────────────────────────────────────────────────────────────
  var bubble = document.createElement("button");
  bubble.id = "typebot-bubble";
  bubble.setAttribute("aria-label", "Chat \u00f6ffnen");
  bubble.innerHTML = '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.2L4 17.2V4h16v12z"/><path d="M7 9h2v2H7zm4 0h2v2h-2zm4 0h2v2h-2z"/></svg>';
  bubble.onclick = function () { openChat(); };
  document.body.appendChild(bubble);

  // ── Preview ─────────────────────────────────────────────────────────────
  var preview = document.createElement("div");
  preview.id = "typebot-preview";
  preview.innerHTML = 'Hallo! Kann ich Ihnen helfen?<button id="typebot-preview-close">&times;</button>';
  preview.onclick = function (e) { if (e.target.id !== "typebot-preview-close") { openChat(); } else { preview.classList.remove("show"); } };
  document.body.appendChild(preview);

  // ── Window ──────────────────────────────────────────────────────────────
  var win = document.createElement("div");
  win.id = "typebot-win";
  win.innerHTML =
    '<div class="tb-hdr">' +
      '<button class="tb-hdr-back" id="tb-back">\u2190</button>' +
      '<div class="tb-hdr-av">\uD83E\uDD16</div>' +
      '<div class="tb-hdr-txt"><div class="tb-hdr-name">EPPCOM Assistent</div><div class="tb-hdr-sub" id="tb-hdr-sub">KI-Assistent \u2014 DSGVO-konform</div></div>' +
      '<button class="tb-hdr-x" id="tb-close">\u00D7</button>' +
    '</div>' +
    '<div id="tb-body" style="flex:1;display:flex;flex-direction:column;overflow:hidden">' +
      '<div id="tb-mode-select" class="tb-mode-select">' +
        '<div class="tb-msg tb-bot">' +
          '<div class="tb-bot-av">\uD83E\uDD16</div>' +
          '<div class="tb-bot-bubble" id="tb-welcome-text"></div>' +
        '</div>' +
        '<div class="tb-msg tb-bot">' +
          '<div class="tb-bot-av">\uD83E\uDD16</div>' +
          '<div class="tb-bot-bubble">Wollen Sie mit mir sprechen oder lieber Ihre Tastatur benutzen?</div>' +
        '</div>' +
        '<div class="tb-choice-row">' +
          '<button class="tb-choice-btn" id="tb-mode-voice">\uD83C\uDF99\uFE0F Sprechen</button>' +
          '<button class="tb-choice-btn" id="tb-mode-text">\u2328\uFE0F Schreiben</button>' +
        '</div>' +
      '</div>' +
      '<div id="tb-chat-view" style="display:none;flex:1;flex-direction:column;overflow:hidden">' +
        '<div class="tb-msgs" id="tb-msgs"></div>' +
        '<div class="tb-input-row">' +
          '<textarea class="tb-inp" id="tb-inp" rows="1" placeholder="Ihre Nachricht..." enterkeyhint="send"></textarea>' +
          '<button class="tb-send" id="tb-send" aria-label="Senden">\u27A4</button>' +
        '</div>' +
      '</div>' +
      '<div id="tb-voice-view" style="display:none;flex:1;flex-direction:column;overflow:hidden">' +
        '<div class="tb-voice-area">' +
          '<button class="tb-voice-btn idle" id="tb-voice-btn" aria-label="Mikrofon">\uD83C\uDF99\uFE0F</button>' +
          '<div class="tb-voice-status" id="tb-voice-status">Antippen zum Starten</div>' +
        '</div>' +
        '<div id="tb-voice-audio"></div>' +
      '</div>' +
    '</div>' +
    '<div class="tb-foot">Powered by EPPCOM Solutions</div>';
  document.body.appendChild(win);

  document.getElementById("tb-welcome-text").textContent = WELCOME;

  // ── Events ──────────────────────────────────────────────────────────────
  document.getElementById("tb-send").onclick = sendMessage;
  document.getElementById("tb-close").onclick = closeChat;
  document.getElementById("tb-back").onclick = goBack;
  document.getElementById("tb-mode-text").onclick = function () { switchMode("text"); };
  document.getElementById("tb-mode-voice").onclick = function () { switchMode("voice"); };
  document.getElementById("tb-voice-btn").onclick = toggleVoice;

  var inp = document.getElementById("tb-inp");
  inp.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  inp.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 80) + "px";
  });
  inp.addEventListener("focus", function () {
    if (isMobile) setTimeout(function () { inp.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, 300);
  });

  // Auto-open
  if (AUTO_OPEN) {
    setTimeout(function () { if (!isOpen) openChat(); }, 2500);
  } else {
    setTimeout(function () { if (!isOpen) preview.classList.add("show"); }, 5000);
  }

  // ── Open / Close ────────────────────────────────────────────────────────
  function openChat() {
    isOpen = true;
    win.classList.add("open");
    preview.classList.remove("show");
    bubble.style.display = "none";
    // Trigger animation on next frame
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { win.classList.add("visible"); });
    });
    if (isMobile) document.body.style.overflow = "hidden";
  }

  function closeChat() {
    win.classList.remove("visible");
    setTimeout(function () {
      isOpen = false;
      win.classList.remove("open");
      bubble.style.display = "flex";
    }, 250);
    if (voiceRoom) stopVoice();
    if (isMobile) document.body.style.overflow = "";
  }

  function goBack() {
    if (voiceRoom) stopVoice();
    mode = null;
    document.getElementById("tb-mode-select").style.display = "flex";
    document.getElementById("tb-chat-view").style.display = "none";
    document.getElementById("tb-voice-view").style.display = "none";
    document.getElementById("tb-back").classList.remove("show");
    document.getElementById("tb-hdr-sub").textContent = "KI-Assistent \u2014 DSGVO-konform";
  }

  function switchMode(m) {
    mode = m;
    document.getElementById("tb-mode-select").style.display = "none";
    document.getElementById("tb-back").classList.add("show");

    if (m === "text") {
      document.getElementById("tb-chat-view").style.display = "flex";
      document.getElementById("tb-voice-view").style.display = "none";
      document.getElementById("tb-hdr-sub").textContent = "Text-Chat";
      if (!document.getElementById("tb-msgs").hasChildNodes()) {
        addBot("Wie kann ich Ihnen helfen? Stellen Sie mir eine Frage.");
      }
      if (!isMobile) inp.focus();
    } else {
      document.getElementById("tb-chat-view").style.display = "none";
      document.getElementById("tb-voice-view").style.display = "flex";
      document.getElementById("tb-hdr-sub").textContent = "Sprach-Chat";
      startVoice();
    }
  }

  // ── Text Chat ───────────────────────────────────────────────────────────
  function addBot(text) {
    var msgs = document.getElementById("tb-msgs");
    var w = document.createElement("div");
    w.className = "tb-msg tb-bot";
    w.innerHTML = '<div class="tb-bot-av">\uD83E\uDD16</div><div class="tb-bot-bubble"></div>';
    w.querySelector(".tb-bot-bubble").textContent = text;
    msgs.appendChild(w);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function addUser(text) {
    var msgs = document.getElementById("tb-msgs");
    var w = document.createElement("div");
    w.className = "tb-msg tb-user";
    w.innerHTML = '<div class="tb-user-bubble"></div>';
    w.querySelector(".tb-user-bubble").textContent = text;
    msgs.appendChild(w);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function addError(text) {
    var msgs = document.getElementById("tb-msgs");
    var w = document.createElement("div");
    w.className = "tb-msg tb-err";
    w.innerHTML = '<div class="tb-bot-av">\u26A0\uFE0F</div><div class="tb-bot-bubble"></div>';
    w.querySelector(".tb-bot-bubble").textContent = text;
    msgs.appendChild(w);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function showTyping() {
    var msgs = document.getElementById("tb-msgs");
    var d = document.createElement("div");
    d.className = "tb-typing"; d.id = "tb-typing";
    d.innerHTML = "<span></span><span></span><span></span>";
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function removeTyping() {
    var el = document.getElementById("tb-typing");
    if (el) el.remove();
  }

  function sendMessage() {
    var text = inp.value.trim();
    if (!text || isLoading) return;

    addUser(text);
    inp.value = "";
    inp.style.height = "auto";
    document.getElementById("tb-send").disabled = true;
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
    .catch(function () {
      removeTyping();
      addError("Es gab einen Fehler. Bitte versuchen Sie es erneut.");
    })
    .finally(function () {
      document.getElementById("tb-send").disabled = false;
      isLoading = false;
    });
  }

  // ── Voice ───────────────────────────────────────────────────────────────
  function setVoiceState(state, statusText) {
    var btn = document.getElementById("tb-voice-btn");
    var st = document.getElementById("tb-voice-status");
    btn.className = "tb-voice-btn " + state;
    st.textContent = statusText;
    st.className = "tb-voice-status" + (state === "active" ? " connected" : "");
  }

  function toggleVoice() { voiceRoom ? stopVoice() : startVoice(); }

  function startVoice() {
    if (voiceConnecting || voiceRoom) return;
    voiceConnecting = true;
    setVoiceState("connecting", "Verbinde...");

    loadLiveKitSDK()
    .then(function () {
      return fetch(VOICE_TOKEN_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identity: "widget-" + SESSION, room: "eppcom-voice" })
      });
    })
    .then(function (res) {
      if (!res.ok) throw new Error("Token-Fehler: " + res.status);
      return res.json();
    })
    .then(function (data) {
      if (!data.token) throw new Error("Kein Token erhalten");
      setVoiceState("connecting", "Verbinde...");

      var room = new LivekitClient.Room();
      voiceRoom = room;

      room.on(LivekitClient.RoomEvent.TrackSubscribed, function (track) {
        if (track.kind === LivekitClient.Track.Kind.Audio) {
          var el = track.attach();
          el.autoplay = true;
          el.volume = 1.0;
          el.setAttribute("playsinline", "");
          document.getElementById("tb-voice-audio").appendChild(el);
        }
      });

      room.on(LivekitClient.RoomEvent.TrackUnsubscribed, function (track) {
        track.detach().forEach(function (el) { el.remove(); });
      });

      room.on(LivekitClient.RoomEvent.ParticipantConnected, function () {
        setVoiceState("active", "Agent verbunden \u2014 sprechen Sie!");
      });

      room.on(LivekitClient.RoomEvent.Disconnected, function () {
        voiceRoom = null;
        voiceConnecting = false;
        setVoiceState("idle", "Getrennt. Antippen zum Neustart.");
      });

      return room.connect(data.url || LIVEKIT_URL, data.token).then(function () {
        return room.localParticipant.setMicrophoneEnabled(true);
      }).then(function () {
        voiceConnecting = false;
        setVoiceState("active", "Verbunden \u2014 sprechen Sie!");
      });
    })
    .catch(function (err) {
      voiceConnecting = false;
      voiceRoom = null;
      setVoiceState("idle", "Fehler: " + ((err && err.message) || err));
      console.error("[EPPCOM Voice]", err);
    });
  }

  function stopVoice() {
    if (voiceRoom) { voiceRoom.disconnect(); voiceRoom = null; }
    voiceConnecting = false;
    setVoiceState("idle", "Beendet. Antippen zum Neustart.");
    var ac = document.getElementById("tb-voice-audio");
    if (ac) ac.innerHTML = "";
  }

  function loadLiveKitSDK() {
    if (window.LivekitClient) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.umd.min.js";
      s.onload = function () { window.LivekitClient ? resolve() : reject(new Error("SDK nicht verf\u00fcgbar")); };
      s.onerror = function () { reject(new Error("SDK konnte nicht geladen werden")); };
      document.head.appendChild(s);
    });
  }
})();
