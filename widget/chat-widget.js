/**
 * EPPCOM RAG Chat-Widget (Text + Voice)
 * Exakt im Original-Typebot-Bubble-Stil
 *
 * Einbindung (vor </body>):
 *   <script src="https://appdb.eppcom.de/widget/chat-widget.js"
 *           data-api-url="https://appdb.eppcom.de/api/public/widget-chat"
 *           data-voice-token-url="https://appdb.eppcom.de/api/public/voice-token"
 *           data-livekit-url="wss://voice.eppcom.de"
 *           data-color="#0042DA"
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
  var COLOR = (script && (script.getAttribute("data-color") || script.getAttribute("data-accent"))) || "#0042DA";
  var WELCOME = (script && script.getAttribute("data-welcome")) || "Hallo! Willkommen bei EPPCOM Solutions \u2014 Ihrem Partner f\u00fcr KI-Automatisierung.";
  var AUTO_OPEN = (script && script.getAttribute("data-auto-open")) !== "false";

  var SESSION = "web_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
  var isOpen = false;
  var isLoading = false;
  var mode = null;
  var voiceRoom = null;
  var voiceConnecting = false;
  var isMobile = /Android|iPhone|iPad|iPod|Opera Mini|IEMobile/i.test(navigator.userAgent) || window.innerWidth < 640;

  // ── CSS (Original Typebot-Bubble-Stil) ──────────────────────────────────
  var css = [
    /* Reset */
    "#typebot-bubble,#typebot-bubble *,#typebot-container,#typebot-container *,#typebot-proactive{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}",

    /* ─── Bubble Button (Typebot Standard) ─── */
    "#typebot-bubble{position:fixed;bottom:20px;right:20px;z-index:42424242;width:56px;height:56px;border-radius:50%;background:CL;color:#fff;border:none;cursor:pointer;box-shadow:0 4px 8px rgba(0,0,0,.12),0 2px 4px rgba(0,0,0,.08);display:flex;align-items:center;justify-content:center;transition:transform .2s,box-shadow .2s;-webkit-appearance:none}",
    "#typebot-bubble:hover{transform:scale(1.05);box-shadow:0 6px 12px rgba(0,0,0,.15)}",
    "#typebot-bubble:active{transform:scale(.95)}",
    "#typebot-bubble svg{width:28px;height:28px;fill:none;stroke:#fff;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}",

    /* ─── Proactive Message (Typebot-Style) ─── */
    "#typebot-proactive{position:fixed;bottom:86px;right:20px;z-index:42424241;background:#fff;border-radius:8px;padding:10px 40px 10px 14px;box-shadow:0 2px 6px rgba(0,0,0,.08),0 0 0 1px rgba(0,0,0,.04);font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#303235;max-width:260px;cursor:pointer;opacity:0;transform:translateY(8px);transition:opacity .3s,transform .3s;pointer-events:none}",
    "#typebot-proactive.show{opacity:1;transform:translateY(0);pointer-events:auto}",
    "#typebot-proactive-x{position:absolute;top:2px;right:8px;background:none;border:none;font-size:18px;cursor:pointer;color:#999;line-height:1;padding:4px}",
    "#typebot-proactive-x:hover{color:#333}",

    /* ─── Chat Container (Typebot Bubble Window) ─── */
    "#typebot-container{position:fixed;bottom:88px;right:20px;z-index:42424242;width:400px;max-height:calc(100vh - 100px);background:#fff;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.12),0 0 0 1px rgba(0,0,0,.05);display:none;flex-direction:column;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;opacity:0;transform:translateY(16px);transition:opacity .2s ease,transform .2s ease}",
    "#typebot-container.open{display:flex}",
    "#typebot-container.visible{opacity:1;transform:translateY(0)}",

    /* Mobile: Vollbild */
    "@media(max-width:640px){" +
      "#typebot-container{top:0;left:0;right:0;bottom:0;width:100%;max-height:none;border-radius:0;box-shadow:none;bottom:0}" +
      "#typebot-bubble{bottom:16px;right:16px}" +
      "#typebot-proactive{bottom:82px;right:16px;max-width:220px}" +
    "}",

    /* Safe area */
    "@supports(padding-top:env(safe-area-inset-top)){@media(max-width:640px){" +
      ".tb-hdr{padding-top:calc(12px + env(safe-area-inset-top))}" +
      ".tb-input-row{padding-bottom:calc(8px + env(safe-area-inset-bottom))}" +
    "}}",

    /* ─── Header (Typebot Standard — weiß mit Bot-Info) ─── */
    ".tb-hdr{display:flex;align-items:center;gap:10px;padding:12px 14px;border-bottom:1px solid #eee;flex-shrink:0;background:#fff}",
    ".tb-hdr-av{width:36px;height:36px;border-radius:50%;background:CL;display:flex;align-items:center;justify-content:center;flex-shrink:0}",
    ".tb-hdr-av svg{width:20px;height:20px;fill:none;stroke:#fff;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}",
    ".tb-hdr-txt{flex:1;min-width:0}",
    ".tb-hdr-name{font-size:15px;font-weight:600;color:#303235;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".tb-hdr-sub{font-size:12px;color:#71717a;margin-top:1px}",
    ".tb-hdr-x,.tb-hdr-back{background:none;border:none;color:#71717a;font-size:20px;cursor:pointer;padding:4px 6px;line-height:1;flex-shrink:0;-webkit-appearance:none;transition:color .15s}",
    ".tb-hdr-x:hover,.tb-hdr-back:hover{color:#303235}",
    ".tb-hdr-back{display:none;font-size:18px}",
    ".tb-hdr-back.show{display:block}",

    /* ─── Messages ─── */
    ".tb-msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:8px;background:#fff;min-height:0;-webkit-overflow-scrolling:touch}",
    ".tb-msg{max-width:84%;font-size:14px;line-height:1.5;word-break:break-word;animation:tb-fade .25s ease}",
    "@keyframes tb-fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}",

    /* Bot */
    ".tb-bot{align-self:flex-start}",
    ".tb-bot-bubble{background:#F7F8FF;color:#303235;padding:10px 14px;border-radius:4px 18px 18px 4px;white-space:pre-wrap}",

    /* User */
    ".tb-user{align-self:flex-end}",
    ".tb-user-bubble{background:CL;color:#fff;padding:10px 14px;border-radius:18px 4px 4px 18px;white-space:pre-wrap}",

    /* Error */
    ".tb-err{align-self:flex-start}",
    ".tb-err .tb-bot-bubble{background:#fef2f2;color:#991b1b}",

    /* Typing indicator */
    ".tb-typing{display:flex;gap:4px;padding:10px 14px;background:#F7F8FF;border-radius:4px 18px 18px 4px;align-self:flex-start}",
    ".tb-typing span{width:6px;height:6px;background:#b0b3b8;border-radius:50%;animation:tb-dot .6s infinite alternate}",
    ".tb-typing span:nth-child(2){animation-delay:.15s}",
    ".tb-typing span:nth-child(3){animation-delay:.3s}",
    "@keyframes tb-dot{to{opacity:.3;transform:translateY(-2px)}}",

    /* ─── Input ─── */
    ".tb-input-row{display:flex;align-items:flex-end;border-top:1px solid #eee;padding:8px 10px;gap:6px;background:#fff;flex-shrink:0}",
    ".tb-inp{flex:1;border:1px solid #e4e4e7;border-radius:8px;padding:8px 12px;font-size:14px;font-family:inherit;resize:none;outline:none;max-height:80px;background:#fff;color:#303235;-webkit-appearance:none;transition:border-color .15s}",
    ".tb-inp::placeholder{color:#a1a1aa}",
    ".tb-inp:focus{border-color:CL}",
    ".tb-send{background:CL;color:#fff;border:none;border-radius:8px;width:36px;height:36px;min-width:36px;cursor:pointer;font-size:15px;display:flex;align-items:center;justify-content:center;transition:opacity .15s;-webkit-appearance:none}",
    ".tb-send:disabled{opacity:.4;cursor:not-allowed}",
    ".tb-foot{text-align:center;padding:4px 0 6px;font-size:10px;color:#a1a1aa;background:#fff;flex-shrink:0}",
    ".tb-foot a{color:#a1a1aa;text-decoration:none}",
    ".tb-foot a:hover{text-decoration:underline}",

    /* ─── Mode Selection (Typebot Button-Input) ─── */
    ".tb-mode-area{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:8px;background:#fff;-webkit-overflow-scrolling:touch}",
    ".tb-choice-row{display:flex;flex-wrap:wrap;gap:6px;animation:tb-fade .25s ease}",
    ".tb-choice-btn{padding:8px 16px;border-radius:8px;border:1px solid CL;background:#fff;color:CL;cursor:pointer;font-size:13px;font-weight:500;font-family:inherit;transition:all .15s ease;-webkit-appearance:none}",
    ".tb-choice-btn:hover{background:CL;color:#fff}",
    ".tb-choice-btn:active{transform:scale(.97)}",

    /* ─── Voice ─── */
    ".tb-voice-area{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:24px}",
    ".tb-voice-btn{width:72px;height:72px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s ease;font-size:28px;-webkit-appearance:none}",
    ".tb-voice-btn:active{transform:scale(.92)}",
    ".tb-voice-btn.idle{background:#f4f4f5;color:#71717a}",
    ".tb-voice-btn.connecting{background:#fbbf24;color:#fff;animation:tb-pulse 1.5s infinite}",
    ".tb-voice-btn.active{background:#ef4444;color:#fff;animation:tb-pulse 1.5s infinite}",
    "@keyframes tb-pulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.3)}50%{box-shadow:0 0 0 12px rgba(239,68,68,0)}}",
    ".tb-voice-status{font-size:13px;color:#71717a;text-align:center}",
    ".tb-voice-status.connected{color:#059669;font-weight:500}",
    "#tb-voice-audio{display:none}"
  ].join("\n").replace(/CL/g, COLOR);

  var styleEl = document.createElement("style");
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  if (!document.querySelector('meta[name="viewport"]')) {
    var meta = document.createElement("meta");
    meta.name = "viewport";
    meta.content = "width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no";
    document.head.appendChild(meta);
  }

  // Typebot chat-bubble SVG icon
  var chatSVG = '<svg viewBox="0 0 24 24"><path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"/></svg>';

  // ── Bubble Button ─────────────────────────────────────────────────────
  var bubble = document.createElement("button");
  bubble.id = "typebot-bubble";
  bubble.setAttribute("aria-label", "Chat \u00f6ffnen");
  bubble.innerHTML = chatSVG;
  bubble.onclick = function () { openChat(); };
  document.body.appendChild(bubble);

  // ── Proactive Message ─────────────────────────────────────────────────
  var proactive = document.createElement("div");
  proactive.id = "typebot-proactive";
  proactive.innerHTML = '\uD83D\uDCAC Fragen Sie unseren KI-Assistenten!<button id="typebot-proactive-x">&times;</button>';
  proactive.onclick = function (e) { if (e.target.id !== "typebot-proactive-x") { openChat(); } else { proactive.classList.remove("show"); } };
  document.body.appendChild(proactive);

  // ── Chat Window ───────────────────────────────────────────────────────
  var win = document.createElement("div");
  win.id = "typebot-container";
  win.innerHTML =
    '<div class="tb-hdr">' +
      '<button class="tb-hdr-back" id="tb-back">\u2190</button>' +
      '<div class="tb-hdr-av">' + chatSVG + '</div>' +
      '<div class="tb-hdr-txt"><div class="tb-hdr-name">EPPCOM Assistent</div><div class="tb-hdr-sub" id="tb-hdr-sub">Immer f\u00fcr Sie da</div></div>' +
      '<button class="tb-hdr-x" id="tb-close">\u00D7</button>' +
    '</div>' +
    '<div id="tb-body" style="flex:1;display:flex;flex-direction:column;overflow:hidden;min-height:0">' +
      /* Mode select — Typebot-Konversationsstil */
      '<div id="tb-mode-select" class="tb-mode-area">' +
        '<div class="tb-msg tb-bot"><div class="tb-bot-bubble" id="tb-welcome-text"></div></div>' +
        '<div class="tb-msg tb-bot"><div class="tb-bot-bubble">Wollen Sie mit mir sprechen oder lieber Ihre Tastatur benutzen?</div></div>' +
        '<div class="tb-choice-row">' +
          '<button class="tb-choice-btn" id="tb-mode-voice">\uD83C\uDF99\uFE0F Sprechen</button>' +
          '<button class="tb-choice-btn" id="tb-mode-text">\u2328\uFE0F Schreiben</button>' +
        '</div>' +
      '</div>' +
      /* Text chat */
      '<div id="tb-chat-view" style="display:none;flex:1;flex-direction:column;overflow:hidden;min-height:0">' +
        '<div class="tb-msgs" id="tb-msgs"></div>' +
        '<div class="tb-input-row">' +
          '<textarea class="tb-inp" id="tb-inp" rows="1" placeholder="Ihre Nachricht\u2026" enterkeyhint="send"></textarea>' +
          '<button class="tb-send" id="tb-send" aria-label="Senden">\u27A4</button>' +
        '</div>' +
      '</div>' +
      /* Voice */
      '<div id="tb-voice-view" style="display:none;flex:1;flex-direction:column;overflow:hidden">' +
        '<div class="tb-voice-area">' +
          '<button class="tb-voice-btn idle" id="tb-voice-btn" aria-label="Mikrofon">\uD83C\uDF99\uFE0F</button>' +
          '<div class="tb-voice-status" id="tb-voice-status">Antippen zum Starten</div>' +
        '</div>' +
        '<div id="tb-voice-audio"></div>' +
      '</div>' +
    '</div>' +
    '<div class="tb-foot">Powered by <a href="https://eppcom.de" target="_blank" rel="noopener">EPPCOM Solutions</a></div>';
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
    setTimeout(function () { if (!isOpen) proactive.classList.add("show"); }, 5000);
  }

  // ── Open / Close ──────────────────────────────────────────────────────
  function openChat() {
    isOpen = true;
    win.classList.add("open");
    proactive.classList.remove("show");
    bubble.style.display = "none";
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
    }, 200);
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
    document.getElementById("tb-hdr-sub").textContent = "Immer f\u00fcr Sie da";
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
        addBot("Wie kann ich Ihnen helfen? Stellen Sie mir eine Frage \u00fcber EPPCOM.");
      }
      if (!isMobile) inp.focus();
    } else {
      document.getElementById("tb-chat-view").style.display = "none";
      document.getElementById("tb-voice-view").style.display = "flex";
      document.getElementById("tb-hdr-sub").textContent = "Sprach-Chat";
      startVoice();
    }
  }

  // ── Text Chat ─────────────────────────────────────────────────────────
  function addBot(text) {
    var msgs = document.getElementById("tb-msgs");
    var w = document.createElement("div");
    w.className = "tb-msg tb-bot";
    w.innerHTML = '<div class="tb-bot-bubble"></div>';
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
    w.innerHTML = '<div class="tb-bot-bubble"></div>';
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
    .catch(function (err) {
      removeTyping();
      addError("Fehler: " + ((err && err.message) || "Bitte versuchen Sie es erneut."));
      console.error("[EPPCOM Chat]", err);
    })
    .finally(function () {
      document.getElementById("tb-send").disabled = false;
      isLoading = false;
    });
  }

  // ── Voice ─────────────────────────────────────────────────────────────
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
    setVoiceState("connecting", "Verbinde\u2026");

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
