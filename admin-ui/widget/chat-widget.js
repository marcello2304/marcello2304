/**
 * EPPCOM RAG Chat-Widget (Text + Voice) — Mobile-optimiert
 *
 * Einbindung auf der Homepage (vor </body>):
 *   <script src="https://appdb.eppcom.de/widget/chat-widget.js"
 *           data-api-url="https://appdb.eppcom.de/api/public/widget-chat"
 *           data-voice-token-url="https://appdb.eppcom.de/api/public/voice-token"
 *           data-livekit-url="wss://voice.eppcom.de"
 *           data-accent="#2563EB"
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
  var ACCENT = (script && script.getAttribute("data-accent")) || "#2563EB";
  var WELCOME = (script && script.getAttribute("data-welcome")) || "Hallo! Willkommen bei EPPCOM Solutions \u2014 Ihrem Partner f\u00fcr KI-Automatisierung.\nWie m\u00f6chten Sie kommunizieren?";
  var AUTO_OPEN = (script && script.getAttribute("data-auto-open")) !== "false";

  var SESSION = "web_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
  var isOpen = false;
  var isLoading = false;
  var mode = null;
  var voiceRoom = null;
  var voiceConnecting = false;
  var isMobile = /Android|iPhone|iPad|iPod|Opera Mini|IEMobile/i.test(navigator.userAgent) || window.innerWidth < 640;

  // ── CSS ─────────────────────────────────────────────────────────────────
  var css = [
    /* Reset within widget */
    "#eppcom-cb,#eppcom-cb *,#eppcom-win,#eppcom-win *,#eppcom-preview{box-sizing:border-box;-webkit-tap-highlight-color:transparent}",

    /* Bubble */
    "#eppcom-cb{position:fixed;bottom:20px;right:20px;z-index:99999;width:56px;height:56px;border-radius:50%;background:VAR;color:#fff;border:none;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.25);display:flex;align-items:center;justify-content:center;transition:transform .15s ease;-webkit-appearance:none}",
    "#eppcom-cb:hover{transform:scale(1.08)}",
    "#eppcom-cb:active{transform:scale(.95)}",
    "#eppcom-cb svg{width:26px;height:26px;fill:currentColor}",

    /* Preview */
    "#eppcom-preview{position:fixed;bottom:86px;right:20px;z-index:99998;background:#fff;border-radius:12px;padding:12px 16px;box-shadow:0 2px 12px rgba(0,0,0,.12);font:14px/1.5 Inter,system-ui,sans-serif;color:#1e293b;max-width:240px;cursor:pointer;display:none}",
    "#eppcom-preview.show{display:block}",
    "#eppcom-preview-close{position:absolute;top:2px;right:6px;background:none;border:none;font-size:18px;cursor:pointer;color:#94a3b8;line-height:1;padding:4px}",

    /* Window — Desktop */
    "#eppcom-win{position:fixed;bottom:88px;right:20px;z-index:99999;width:380px;height:540px;background:#fff;border-radius:16px;box-shadow:0 8px 30px rgba(0,0,0,.18);display:none;flex-direction:column;overflow:hidden;font-family:Inter,system-ui,-apple-system,sans-serif;-webkit-overflow-scrolling:touch}",
    "#eppcom-win.open{display:flex}",

    /* Window — Mobile: Vollbild */
    "@media(max-width:640px){" +
      "#eppcom-win{top:0;left:0;right:0;bottom:0;width:100%;height:100%;max-width:none;max-height:none;border-radius:0;box-shadow:none}" +
      "#eppcom-cb{bottom:16px;right:16px;width:52px;height:52px}" +
      "#eppcom-preview{bottom:78px;right:16px;max-width:200px}" +
      ".ec-mode-select{padding:20px 16px!important}" +
      ".ec-mode-btn{padding:14px 16px!important}" +
      ".ec-msgs{padding:12px!important}" +
      ".ec-voice-area{padding:20px 16px!important}" +
    "}",

    /* Safe area (Notch) */
    "@supports(padding-top: env(safe-area-inset-top)){" +
      "@media(max-width:640px){" +
        ".ec-hdr{padding-top:calc(12px + env(safe-area-inset-top))}" +
        ".ec-foot{padding-bottom:calc(6px + env(safe-area-inset-bottom))}" +
        ".ec-input-row{padding-bottom:calc(10px + env(safe-area-inset-bottom))}" +
      "}" +
    "}",

    /* Header */
    ".ec-hdr{background:VAR;color:#fff;padding:12px 14px;display:flex;align-items:center;gap:8px;flex-shrink:0}",
    ".ec-hdr-av{width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,.18);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}",
    ".ec-hdr-txt{flex:1;min-width:0}",
    ".ec-hdr-name{font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".ec-hdr-sub{font-size:11px;opacity:.75;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".ec-hdr-x,.ec-hdr-back{background:none;border:none;color:#fff;font-size:20px;cursor:pointer;padding:6px 8px;opacity:.7;line-height:1;flex-shrink:0;-webkit-appearance:none}",
    ".ec-hdr-x:hover,.ec-hdr-back:hover,.ec-hdr-x:active,.ec-hdr-back:active{opacity:1}",
    ".ec-hdr-back{display:none;font-size:18px}",
    ".ec-hdr-back.show{display:block}",

    /* Messages */
    ".ec-msgs{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#fff;-webkit-overflow-scrolling:touch}",
    ".ec-msg{max-width:85%;font-size:14px;line-height:1.5;word-break:break-word}",
    ".ec-bot{align-self:flex-start;display:flex;gap:8px;align-items:flex-end}",
    ".ec-bot-av{width:28px;height:28px;border-radius:50%;background:VAR;display:flex;align-items:center;justify-content:center;font-size:13px;color:#fff;flex-shrink:0}",
    ".ec-bot-bubble{background:#F0F4FF;color:#1E293B;padding:10px 14px;border-radius:6px 12px 12px 6px;white-space:pre-wrap}",
    ".ec-user{align-self:flex-end}",
    ".ec-user-bubble{background:VAR;color:#fff;padding:10px 14px;border-radius:12px 6px 6px 12px;white-space:pre-wrap}",
    ".ec-err{align-self:flex-start;display:flex;gap:8px;align-items:flex-end}",
    ".ec-err .ec-bot-bubble{background:#fef2f2;color:#991b1b}",

    /* Typing */
    ".ec-typing{display:flex;gap:5px;padding:10px 14px;background:#F0F4FF;border-radius:6px 12px 12px 6px;align-self:flex-start;margin-left:36px}",
    ".ec-typing span{width:7px;height:7px;background:#94a3b8;border-radius:50%;animation:ecb .6s infinite alternate}",
    ".ec-typing span:nth-child(2){animation-delay:.15s}",
    ".ec-typing span:nth-child(3){animation-delay:.3s}",
    "@keyframes ecb{to{opacity:.3;transform:translateY(-3px)}}",

    /* Input */
    ".ec-input-row{display:flex;border-top:1px solid #e2e8f0;padding:8px 10px;gap:8px;background:#fff;flex-shrink:0}",
    ".ec-inp{flex:1;border:1px solid #e2e8f0;border-radius:10px;padding:10px 12px;font-size:16px;font-family:inherit;resize:none;outline:none;max-height:80px;background:#fff;color:#1E293B;-webkit-appearance:none}",
    ".ec-inp::placeholder{color:#9CA3AF}",
    ".ec-inp:focus{border-color:VAR;box-shadow:0 0 0 1px VAR}",
    ".ec-send{background:VAR;color:#fff;border:none;border-radius:10px;padding:0 14px;cursor:pointer;font-size:18px;display:flex;align-items:center;transition:opacity .15s;-webkit-appearance:none;min-width:44px;justify-content:center}",
    ".ec-send:disabled{opacity:.4;cursor:not-allowed}",
    ".ec-foot{text-align:center;padding:4px 0 6px;font-size:10px;color:#94a3b8;background:#fff;flex-shrink:0}",

    /* Mode selection */
    ".ec-mode-select{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:24px}",
    ".ec-mode-btn{width:100%;max-width:280px;padding:16px 20px;border-radius:12px;border:2px solid #e2e8f0;background:#fff;cursor:pointer;display:flex;align-items:center;gap:14px;transition:all .15s ease;font-family:inherit;-webkit-appearance:none;min-height:48px}",
    ".ec-mode-btn:hover,.ec-mode-btn:active{border-color:VAR;background:#f8faff}",
    ".ec-mode-btn:active{transform:scale(.98)}",
    ".ec-mode-icon{width:44px;height:44px;border-radius:12px;background:VAR;color:#fff;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0}",
    ".ec-mode-label{text-align:left;min-width:0}",
    ".ec-mode-title{font-size:15px;font-weight:600;color:#1e293b}",
    ".ec-mode-desc{font-size:12px;color:#64748b;margin-top:2px}",

    /* Voice UI */
    ".ec-voice-area{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:24px}",
    ".ec-voice-btn{width:80px;height:80px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s ease;font-size:32px;-webkit-appearance:none}",
    ".ec-voice-btn:active{transform:scale(.92)}",
    ".ec-voice-btn.idle{background:#e2e8f0;color:#64748b}",
    ".ec-voice-btn.connecting{background:#fbbf24;color:#fff;animation:ec-pulse 1.5s infinite}",
    ".ec-voice-btn.active{background:#ef4444;color:#fff;animation:ec-pulse 1.5s infinite}",
    "@keyframes ec-pulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.4)}50%{box-shadow:0 0 0 14px rgba(239,68,68,0)}}",
    ".ec-voice-status{font-size:14px;color:#64748b;text-align:center;padding:0 8px}",
    ".ec-voice-status.connected{color:#059669}",
    "#ec-voice-audio{display:none}"
  ].join("\n").replace(/VAR/g, ACCENT);

  var styleEl = document.createElement("style");
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  // Viewport meta (mobile zoom fix for inputs)
  if (!document.querySelector('meta[name="viewport"]')) {
    var meta = document.createElement("meta");
    meta.name = "viewport";
    meta.content = "width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no";
    document.head.appendChild(meta);
  }

  // ── Bubble ──────────────────────────────────────────────────────────────
  var bubble = document.createElement("button");
  bubble.id = "eppcom-cb";
  bubble.setAttribute("aria-label", "Chat \u00f6ffnen");
  bubble.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 3C6.5 3 2 6.58 2 11a7.23 7.23 0 002.75 5.5L3 21l4.5-2.5A11.27 11.27 0 0012 19c5.5 0 10-3.58 10-8s-4.5-8-10-8z"/></svg>';
  bubble.onclick = function () { openChat(); };
  document.body.appendChild(bubble);

  // ── Preview ─────────────────────────────────────────────────────────────
  var preview = document.createElement("div");
  preview.id = "eppcom-preview";
  preview.innerHTML = 'Hallo! Kann ich Ihnen helfen?<button id="eppcom-preview-close">&times;</button>';
  preview.onclick = function (e) { if (e.target.id !== "eppcom-preview-close") { openChat(); } else { preview.classList.remove("show"); } };
  document.body.appendChild(preview);

  // ── Window ──────────────────────────────────────────────────────────────
  var win = document.createElement("div");
  win.id = "eppcom-win";
  win.innerHTML =
    '<div class="ec-hdr">' +
      '<button class="ec-hdr-back" id="ec-back">\u2190</button>' +
      '<div class="ec-hdr-av">\uD83E\uDD16</div>' +
      '<div class="ec-hdr-txt"><div class="ec-hdr-name">EPPCOM Assistent</div><div class="ec-hdr-sub" id="ec-hdr-sub">KI-Assistent \u2014 DSGVO-konform</div></div>' +
      '<button class="ec-hdr-x" id="eppcom-close">\u00D7</button>' +
    '</div>' +
    '<div id="ec-body" style="flex:1;display:flex;flex-direction:column;overflow:hidden">' +
      '<div id="ec-mode-select" class="ec-mode-select">' +
        '<div class="ec-msg ec-bot" style="max-width:100%;margin-bottom:8px">' +
          '<div class="ec-bot-av">\uD83E\uDD16</div>' +
          '<div class="ec-bot-bubble" id="ec-welcome-text"></div>' +
        '</div>' +
        '<button class="ec-mode-btn" id="ec-mode-text">' +
          '<div class="ec-mode-icon">\u270D\uFE0F</div>' +
          '<div class="ec-mode-label"><div class="ec-mode-title">Schreiben</div><div class="ec-mode-desc">Tippen Sie Ihre Frage ein</div></div>' +
        '</button>' +
        '<button class="ec-mode-btn" id="ec-mode-voice">' +
          '<div class="ec-mode-icon">\uD83C\uDF99\uFE0F</div>' +
          '<div class="ec-mode-label"><div class="ec-mode-title">Sprechen</div><div class="ec-mode-desc">Reden Sie direkt mit dem Assistenten</div></div>' +
        '</button>' +
      '</div>' +
      '<div id="ec-chat-view" style="display:none;flex:1;flex-direction:column;overflow:hidden">' +
        '<div class="ec-msgs" id="ec-msgs"></div>' +
        '<div class="ec-input-row">' +
          '<textarea class="ec-inp" id="ec-inp" rows="1" placeholder="Ihre Frage eingeben..." enterkeyhint="send"></textarea>' +
          '<button class="ec-send" id="ec-send" aria-label="Senden">\u27A4</button>' +
        '</div>' +
      '</div>' +
      '<div id="ec-voice-view" style="display:none;flex:1;flex-direction:column;overflow:hidden">' +
        '<div class="ec-voice-area">' +
          '<button class="ec-voice-btn idle" id="ec-voice-btn" aria-label="Mikrofon">\uD83C\uDF99\uFE0F</button>' +
          '<div class="ec-voice-status" id="ec-voice-status">Antippen zum Starten</div>' +
        '</div>' +
        '<div id="ec-voice-audio"></div>' +
      '</div>' +
    '</div>' +
    '<div class="ec-foot">EPPCOM Solutions \u2014 KI-Automatisierung</div>';
  document.body.appendChild(win);

  document.getElementById("ec-welcome-text").textContent = WELCOME;

  // ── Events ──────────────────────────────────────────────────────────────
  document.getElementById("ec-send").onclick = sendMessage;
  document.getElementById("eppcom-close").onclick = closeChat;
  document.getElementById("ec-back").onclick = goBack;
  document.getElementById("ec-mode-text").onclick = function () { switchMode("text"); };
  document.getElementById("ec-mode-voice").onclick = function () { switchMode("voice"); };
  document.getElementById("ec-voice-btn").onclick = toggleVoice;

  var inp = document.getElementById("ec-inp");
  inp.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  inp.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 80) + "px";
  });
  // Mobile: Scroll to input when keyboard opens
  inp.addEventListener("focus", function () {
    if (isMobile) {
      setTimeout(function () {
        inp.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }, 300);
    }
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
    bubble.style.display = "none";
    preview.classList.remove("show");
    // Mobile: prevent body scroll
    if (isMobile) document.body.style.overflow = "hidden";
  }

  function closeChat() {
    isOpen = false;
    win.classList.remove("open");
    bubble.style.display = "flex";
    if (voiceRoom) stopVoice();
    if (isMobile) document.body.style.overflow = "";
  }

  function goBack() {
    if (voiceRoom) stopVoice();
    mode = null;
    document.getElementById("ec-mode-select").style.display = "flex";
    document.getElementById("ec-chat-view").style.display = "none";
    document.getElementById("ec-voice-view").style.display = "none";
    document.getElementById("ec-back").classList.remove("show");
    document.getElementById("ec-hdr-sub").textContent = "KI-Assistent \u2014 DSGVO-konform";
  }

  function switchMode(m) {
    mode = m;
    document.getElementById("ec-mode-select").style.display = "none";
    document.getElementById("ec-back").classList.add("show");

    if (m === "text") {
      document.getElementById("ec-chat-view").style.display = "flex";
      document.getElementById("ec-voice-view").style.display = "none";
      document.getElementById("ec-hdr-sub").textContent = "Text-Chat";
      if (!document.getElementById("ec-msgs").hasChildNodes()) {
        addBot("Wie kann ich Ihnen helfen? Stellen Sie mir eine Frage.");
      }
      if (!isMobile) document.getElementById("ec-inp").focus();
    } else {
      document.getElementById("ec-chat-view").style.display = "none";
      document.getElementById("ec-voice-view").style.display = "flex";
      document.getElementById("ec-hdr-sub").textContent = "Sprach-Chat";
      startVoice();
    }
  }

  // ── Text Chat ───────────────────────────────────────────────────────────
  function addBot(text) {
    var msgs = document.getElementById("ec-msgs");
    var w = document.createElement("div");
    w.className = "ec-msg ec-bot";
    w.innerHTML = '<div class="ec-bot-av">\uD83E\uDD16</div><div class="ec-bot-bubble"></div>';
    w.querySelector(".ec-bot-bubble").textContent = text;
    msgs.appendChild(w);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function addUser(text) {
    var msgs = document.getElementById("ec-msgs");
    var w = document.createElement("div");
    w.className = "ec-msg ec-user";
    w.innerHTML = '<div class="ec-user-bubble"></div>';
    w.querySelector(".ec-user-bubble").textContent = text;
    msgs.appendChild(w);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function addError(text) {
    var msgs = document.getElementById("ec-msgs");
    var w = document.createElement("div");
    w.className = "ec-msg ec-err";
    w.innerHTML = '<div class="ec-bot-av">\u26A0\uFE0F</div><div class="ec-bot-bubble"></div>';
    w.querySelector(".ec-bot-bubble").textContent = text;
    msgs.appendChild(w);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function showTyping() {
    var msgs = document.getElementById("ec-msgs");
    var d = document.createElement("div");
    d.className = "ec-typing"; d.id = "ec-typing";
    d.innerHTML = "<span></span><span></span><span></span>";
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function removeTyping() {
    var el = document.getElementById("ec-typing");
    if (el) el.remove();
  }

  function sendMessage() {
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
    .catch(function () {
      removeTyping();
      addError("Es gab einen Fehler. Bitte versuchen Sie es erneut.");
    })
    .finally(function () {
      document.getElementById("ec-send").disabled = false;
      isLoading = false;
    });
  }

  // ── Voice ───────────────────────────────────────────────────────────────
  function setVoiceState(state, statusText) {
    var btn = document.getElementById("ec-voice-btn");
    var st = document.getElementById("ec-voice-status");
    btn.className = "ec-voice-btn " + state;
    st.textContent = statusText;
    st.className = "ec-voice-status" + (state === "active" ? " connected" : "");
  }

  function toggleVoice() { voiceRoom ? stopVoice() : startVoice(); }

  function startVoice() {
    if (voiceConnecting || voiceRoom) return;
    voiceConnecting = true;
    setVoiceState("connecting", "Verbinde...");

    loadLiveKitSDK()
    .then(function () {
      setVoiceState("connecting", "Hole Token...");
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
      setVoiceState("connecting", "Verbinde mit Sprachserver...");

      var room = new LivekitClient.Room();
      voiceRoom = room;

      room.on(LivekitClient.RoomEvent.TrackSubscribed, function (track) {
        if (track.kind === LivekitClient.Track.Kind.Audio) {
          var el = track.attach();
          el.autoplay = true;
          el.volume = 1.0;
          el.setAttribute("playsinline", "");
          document.getElementById("ec-voice-audio").appendChild(el);
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
    var ac = document.getElementById("ec-voice-audio");
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
