/**
 * EPPCOM RAG Chat-Widget (Text + Voice)
 * Floating Chat-Bubble mit Schreiben/Sprechen-Auswahl.
 *
 * Einbindung:
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
  var ACCENT  = (script && script.getAttribute("data-accent"))  || "#2563EB";
  var WELCOME = (script && script.getAttribute("data-welcome")) || "Hallo! Willkommen bei EPPCOM Solutions \u2014 Ihrem Partner f\u00fcr KI-Automatisierung.\nWie m\u00f6chten Sie kommunizieren?";
  var AUTO_OPEN = (script && script.getAttribute("data-auto-open")) !== "false";

  var SESSION = "web_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
  var isOpen  = false;
  var isLoading = false;
  var mode = null; // null = auswahl, "text" = chat, "voice" = sprache
  var voiceRoom = null;
  var voiceConnecting = false;

  // ── CSS ─────────────────────────────────────────────────────────────────
  var css = [
    /* Bubble */
    "#eppcom-cb{position:fixed;bottom:24px;right:24px;z-index:99999;width:56px;height:56px;border-radius:50%;background:VAR;color:#fff;border:none;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.2);display:flex;align-items:center;justify-content:center;transition:transform .15s ease}",
    "#eppcom-cb:hover{transform:scale(1.08)}",
    "#eppcom-cb svg{width:26px;height:26px;fill:currentColor}",
    /* Preview message */
    "#eppcom-preview{position:fixed;bottom:90px;right:24px;z-index:99998;background:#fff;border-radius:12px;padding:12px 16px;box-shadow:0 2px 12px rgba(0,0,0,.12);font:14px/1.5 Inter,system-ui,sans-serif;color:#1e293b;max-width:260px;cursor:pointer;display:none}",
    "#eppcom-preview.show{display:block}",
    "#eppcom-preview-close{position:absolute;top:2px;right:6px;background:none;border:none;font-size:16px;cursor:pointer;color:#94a3b8;line-height:1}",
    /* Window */
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
    ".ec-hdr-back{background:none;border:none;color:#fff;font-size:16px;cursor:pointer;padding:4px 6px;opacity:.7;line-height:1;flex-shrink:0;display:none}",
    ".ec-hdr-back:hover{opacity:1}",
    ".ec-hdr-back.show{display:block}",
    /* Messages area */
    ".ec-msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;background:#ffffff}",
    ".ec-msg{max-width:82%;font-size:14px;line-height:1.55;word-break:break-word}",
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
    ".ec-input-row{display:flex;border-top:1px solid #e2e8f0;padding:10px 12px;gap:8px;background:#fff}",
    ".ec-inp{flex:1;border:1px solid #e2e8f0;border-radius:10px;padding:10px 12px;font-size:14px;font-family:inherit;resize:none;outline:none;max-height:80px;background:#fff;color:#1E293B}",
    ".ec-inp::placeholder{color:#9CA3AF}",
    ".ec-inp:focus{border-color:VAR;box-shadow:0 0 0 1px VAR}",
    ".ec-send{background:VAR;color:#fff;border:none;border-radius:10px;padding:0 14px;cursor:pointer;font-size:18px;display:flex;align-items:center;transition:opacity .15s}",
    ".ec-send:disabled{opacity:.4;cursor:not-allowed}",
    ".ec-foot{text-align:center;padding:4px 0 8px;font-size:10px;color:#94a3b8;background:#fff}",
    /* Mode selection */
    ".ec-mode-select{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:24px}",
    ".ec-mode-btn{width:100%;max-width:260px;padding:16px 20px;border-radius:12px;border:2px solid #e2e8f0;background:#fff;cursor:pointer;display:flex;align-items:center;gap:14px;transition:all .15s ease;font-family:inherit}",
    ".ec-mode-btn:hover{border-color:VAR;background:#f8faff;transform:translateY(-1px);box-shadow:0 2px 8px rgba(0,0,0,.08)}",
    ".ec-mode-icon{width:44px;height:44px;border-radius:12px;background:VAR;color:#fff;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0}",
    ".ec-mode-label{text-align:left}",
    ".ec-mode-title{font-size:15px;font-weight:600;color:#1e293b}",
    ".ec-mode-desc{font-size:12px;color:#64748b;margin-top:2px}",
    /* Voice UI */
    ".ec-voice-area{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:24px}",
    ".ec-voice-btn{width:80px;height:80px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s ease;font-size:32px}",
    ".ec-voice-btn.idle{background:#e2e8f0;color:#64748b}",
    ".ec-voice-btn.connecting{background:#fbbf24;color:#fff;animation:ec-pulse 1.5s infinite}",
    ".ec-voice-btn.active{background:#ef4444;color:#fff;animation:ec-pulse 1.5s infinite}",
    "@keyframes ec-pulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.4)}50%{box-shadow:0 0 0 12px rgba(239,68,68,0)}}",
    ".ec-voice-status{font-size:14px;color:#64748b;text-align:center}",
    ".ec-voice-status.connected{color:#059669}",
    ".ec-voice-transcript{width:100%;max-height:180px;overflow-y:auto;display:flex;flex-direction:column;gap:6px;padding:0 4px}",
    ".ec-voice-msg{font-size:13px;padding:6px 10px;border-radius:8px;max-width:90%}",
    ".ec-voice-msg.user{background:#dbeafe;align-self:flex-end}",
    ".ec-voice-msg.agent{background:#f0f4ff;align-self:flex-start}",
    "#ec-voice-audio{display:none}",
    "@media(max-width:440px){#eppcom-win{right:8px;left:8px;width:auto;bottom:80px;height:calc(100vh - 100px);max-height:none;border-radius:12px}#eppcom-cb{bottom:16px;right:16px}}"
  ].join("\n").replace(/VAR/g, ACCENT);

  var styleEl = document.createElement("style");
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  // ── Bubble ──────────────────────────────────────────────────────────────
  var bubble = document.createElement("button");
  bubble.id = "eppcom-cb";
  bubble.setAttribute("aria-label", "Chat \u00f6ffnen");
  bubble.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 3C6.5 3 2 6.58 2 11a7.23 7.23 0 002.75 5.5L3 21l4.5-2.5A11.27 11.27 0 0012 19c5.5 0 10-3.58 10-8s-4.5-8-10-8z"/></svg>';
  bubble.onclick = function() { openChat(); };
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
      /* Mode selection (initial) */
      '<div id="ec-mode-select" class="ec-mode-select">' +
        '<div class="ec-msg ec-bot" style="max-width:100%;margin-bottom:8px">' +
          '<div class="ec-bot-av">\uD83E\uDD16</div>' +
          '<div class="ec-bot-bubble" id="ec-welcome-text"></div>' +
        '</div>' +
        '<button class="ec-mode-btn" id="ec-mode-text">' +
          '<div class="ec-mode-icon">\u270D\uFE0F</div>' +
          '<div class="ec-mode-label"><div class="ec-mode-title">Schreiben</div><div class="ec-mode-desc">Tippe deine Frage ein</div></div>' +
        '</button>' +
        '<button class="ec-mode-btn" id="ec-mode-voice">' +
          '<div class="ec-mode-icon">\uD83C\uDF99\uFE0F</div>' +
          '<div class="ec-mode-label"><div class="ec-mode-title">Sprechen</div><div class="ec-mode-desc">Rede direkt mit dem Assistenten</div></div>' +
        '</button>' +
      '</div>' +
      /* Chat view (hidden initially) */
      '<div id="ec-chat-view" style="display:none;flex:1;flex-direction:column;overflow:hidden">' +
        '<div class="ec-msgs" id="ec-msgs"></div>' +
        '<div class="ec-input-row">' +
          '<textarea class="ec-inp" id="ec-inp" rows="1" placeholder="Ihre Frage eingeben..."></textarea>' +
          '<button class="ec-send" id="ec-send">\u27A4</button>' +
        '</div>' +
      '</div>' +
      /* Voice view (hidden initially) */
      '<div id="ec-voice-view" style="display:none;flex:1;flex-direction:column;overflow:hidden">' +
        '<div class="ec-voice-area">' +
          '<button class="ec-voice-btn idle" id="ec-voice-btn">\uD83C\uDF99\uFE0F</button>' +
          '<div class="ec-voice-status" id="ec-voice-status">Klicke zum Starten</div>' +
          '<div class="ec-voice-transcript" id="ec-voice-transcript"></div>' +
        '</div>' +
        '<div id="ec-voice-audio"></div>' +
      '</div>' +
    '</div>' +
    '<div class="ec-foot">EPPCOM Solutions \u2014 KI-Automatisierung</div>';
  document.body.appendChild(win);

  // Set welcome text
  document.getElementById("ec-welcome-text").textContent = WELCOME;

  // ── Events ──────────────────────────────────────────────────────────────
  document.getElementById("ec-send").onclick = sendMessage;
  document.getElementById("eppcom-close").onclick = closeChat;
  document.getElementById("ec-back").onclick = goBack;
  document.getElementById("ec-mode-text").onclick = function() { switchMode("text"); };
  document.getElementById("ec-mode-voice").onclick = function() { switchMode("voice"); };
  document.getElementById("ec-voice-btn").onclick = toggleVoice;
  document.getElementById("ec-inp").addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  document.getElementById("ec-inp").addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 80) + "px";
  });

  // Auto-open after delay
  if (AUTO_OPEN) {
    setTimeout(function () {
      if (!isOpen) openChat();
    }, 2000);
  } else {
    setTimeout(function () { if (!isOpen) preview.classList.add("show"); }, 5000);
  }

  // ── Open / Close ──────────────────────────────────────────────────────────
  function openChat() {
    isOpen = true;
    win.classList.add("open");
    bubble.style.display = "none";
    preview.classList.remove("show");
  }

  function closeChat() {
    isOpen = false;
    win.classList.remove("open");
    bubble.style.display = "flex";
    if (voiceRoom) { stopVoice(); }
  }

  function goBack() {
    if (voiceRoom) { stopVoice(); }
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
      document.getElementById("ec-hdr-sub").textContent = "Text-Chat \u2014 DSGVO-konform";
      if (!document.getElementById("ec-msgs").hasChildNodes()) {
        addBot("Wie kann ich Ihnen helfen? Stellen Sie mir eine Frage.");
      }
      document.getElementById("ec-inp").focus();
    } else {
      document.getElementById("ec-chat-view").style.display = "none";
      document.getElementById("ec-voice-view").style.display = "flex";
      document.getElementById("ec-hdr-sub").textContent = "Sprach-Chat \u2014 DSGVO-konform";
      // Auto-start voice
      startVoice();
    }
  }

  // ── Text Chat Functions ─────────────────────────────────────────────────
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

  // ── Voice Functions ─────────────────────────────────────────────────────
  function setVoiceState(state, statusText) {
    var btn = document.getElementById("ec-voice-btn");
    var status = document.getElementById("ec-voice-status");
    btn.className = "ec-voice-btn " + state;
    status.textContent = statusText;
    status.className = "ec-voice-status" + (state === "active" ? " connected" : "");
  }

  function toggleVoice() {
    if (voiceRoom) {
      stopVoice();
    } else {
      startVoice();
    }
  }

  function startVoice() {
    if (voiceConnecting || voiceRoom) return;
    voiceConnecting = true;
    setVoiceState("connecting", "Verbinde...");

    loadLiveKitSDK()
    .then(function() {
      setVoiceState("connecting", "Hole Token...");
      return fetch(VOICE_TOKEN_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          identity: "widget-user-" + SESSION,
          room: "eppcom-voice"
        })
      });
    })
    .then(function(res) {
      if (!res.ok) throw new Error("Token-Fehler: " + res.status);
      return res.json();
    })
    .then(function(data) {
      if (!data.token) throw new Error("Kein Token erhalten");
      setVoiceState("connecting", "Verbinde mit Sprachserver...");

      var room = new LivekitClient.Room();
      voiceRoom = room;

      room.on(LivekitClient.RoomEvent.TrackSubscribed, function(track, pub, participant) {
        if (track.kind === LivekitClient.Track.Kind.Audio) {
          var el = track.attach();
          el.autoplay = true;
          el.volume = 1.0;
          el.id = "ec-voice-track-" + track.sid;
          document.getElementById("ec-voice-audio").appendChild(el);
        }
      });

      room.on(LivekitClient.RoomEvent.TrackUnsubscribed, function(track) {
        track.detach().forEach(function(el) { el.remove(); });
      });

      room.on(LivekitClient.RoomEvent.ParticipantConnected, function(participant) {
        setVoiceState("active", "Agent verbunden \u2014 sprechen Sie!");
      });

      room.on(LivekitClient.RoomEvent.Disconnected, function() {
        voiceRoom = null;
        voiceConnecting = false;
        setVoiceState("idle", "Verbindung getrennt. Klicke zum Neustart.");
      });

      var url = data.url || LIVEKIT_URL;
      return room.connect(url, data.token).then(function() {
        return room.localParticipant.setMicrophoneEnabled(true);
      }).then(function() {
        voiceConnecting = false;
        setVoiceState("active", "Verbunden \u2014 sprechen Sie!");
      });
    })
    .catch(function(err) {
      voiceConnecting = false;
      voiceRoom = null;
      var msg = (err && err.message) || String(err);
      setVoiceState("idle", "Fehler: " + msg);
      console.error("[EPPCOM Voice]", err);
    });
  }

  function stopVoice() {
    if (voiceRoom) {
      voiceRoom.disconnect();
      voiceRoom = null;
    }
    voiceConnecting = false;
    setVoiceState("idle", "Sitzung beendet. Klicke zum Neustart.");
    var audioContainer = document.getElementById("ec-voice-audio");
    if (audioContainer) audioContainer.innerHTML = "";
  }

  function loadLiveKitSDK() {
    if (window.LivekitClient) return Promise.resolve();
    return new Promise(function(resolve, reject) {
      var s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.umd.min.js";
      s.onload = function() {
        if (window.LivekitClient) resolve();
        else reject(new Error("LiveKit SDK geladen aber nicht verf\u00fcgbar"));
      };
      s.onerror = function() { reject(new Error("LiveKit SDK konnte nicht geladen werden")); };
      document.head.appendChild(s);
    });
  }
})();
