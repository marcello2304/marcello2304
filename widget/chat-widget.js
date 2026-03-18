/**
 * EPPCOM Chat + Voice Widget
 * Bei "Schreiben" → echten Typebot-Chatbot öffnen
 * Bei "Sprechen" → LiveKit Voice-Agent starten
 *
 * Einbindung (vor </body>):
 *   <script src="https://appdb.eppcom.de/widget/chat-widget.js"
 *           data-typebot-id="eppcom-chatbot-v2"
 *           data-typebot-host="https://bot.eppcom.de"
 *           data-voice-token-url="https://appdb.eppcom.de/api/public/voice-token"
 *           data-livekit-url="wss://voice.eppcom.de"
 *           data-color="#0042DA"
 *           data-welcome="Hallo! Willkommen bei EPPCOM Solutions — Ihrem Partner für KI-Automatisierung."
 *           data-auto-open="true"
 *           defer></script>
 */
(function () {
  "use strict";

  var script = document.currentScript || document.querySelector("script[data-typebot-id]");
  var TYPEBOT_ID = (script && script.getAttribute("data-typebot-id")) || "eppcom-chatbot-v2";
  var TYPEBOT_HOST = (script && script.getAttribute("data-typebot-host")) || "https://bot.eppcom.de";
  var VOICE_TOKEN_URL = (script && script.getAttribute("data-voice-token-url")) || "https://appdb.eppcom.de/api/public/voice-token";
  var LIVEKIT_URL = (script && script.getAttribute("data-livekit-url")) || "wss://voice.eppcom.de";
  var COLOR = (script && (script.getAttribute("data-color") || script.getAttribute("data-accent"))) || "#0042DA";
  var WELCOME = (script && script.getAttribute("data-welcome")) || "Hallo! Willkommen bei EPPCOM Solutions \u2014 Ihrem Partner f\u00fcr KI-Automatisierung.";
  var AUTO_OPEN = (script && script.getAttribute("data-auto-open")) !== "false";

  var SESSION = "web_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
  var isOpen = false;
  var mode = null;
  var voiceRoom = null;
  var voiceConnecting = false;
  var typebotLoaded = false;
  var isMobile = /Android|iPhone|iPad|iPod|Opera Mini|IEMobile/i.test(navigator.userAgent) || window.innerWidth < 640;

  // ── CSS ───────────────────────────────────────────────────────────────
  var css = [
    "#eppcom-bubble,#eppcom-bubble *,#eppcom-win,#eppcom-win *,#eppcom-proactive{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}",

    /* Bubble */
    "#eppcom-bubble{position:fixed;bottom:20px;right:20px;z-index:42424242;width:56px;height:56px;border-radius:50%;background:CL;color:#fff;border:none;cursor:pointer;box-shadow:0 4px 8px rgba(0,0,0,.12),0 2px 4px rgba(0,0,0,.08);display:flex;align-items:center;justify-content:center;transition:transform .2s,box-shadow .2s;-webkit-appearance:none}",
    "#eppcom-bubble:hover{transform:scale(1.05);box-shadow:0 6px 12px rgba(0,0,0,.15)}",
    "#eppcom-bubble:active{transform:scale(.95)}",
    "#eppcom-bubble svg{width:28px;height:28px;fill:none;stroke:#fff;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}",

    /* Proactive */
    "#eppcom-proactive{position:fixed;bottom:86px;right:20px;z-index:42424241;background:#fff;border-radius:8px;padding:10px 40px 10px 14px;box-shadow:0 2px 6px rgba(0,0,0,.08),0 0 0 1px rgba(0,0,0,.04);font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#303235;max-width:260px;cursor:pointer;opacity:0;transform:translateY(8px);transition:opacity .3s,transform .3s;pointer-events:none}",
    "#eppcom-proactive.show{opacity:1;transform:translateY(0);pointer-events:auto}",
    "#eppcom-proactive-x{position:absolute;top:2px;right:8px;background:none;border:none;font-size:18px;cursor:pointer;color:#999;line-height:1;padding:4px}",

    /* Chat Window (Auswahl + Voice) */
    "#eppcom-win{position:fixed;bottom:88px;right:20px;z-index:42424242;width:400px;max-height:calc(100vh - 100px);height:500px;background:#fff;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.12),0 0 0 1px rgba(0,0,0,.05);display:none;flex-direction:column;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;opacity:0;transform:translateY(16px);transition:opacity .2s ease,transform .2s ease}",
    "#eppcom-win.open{display:flex}",
    "#eppcom-win.visible{opacity:1;transform:translateY(0)}",

    "@media(max-width:640px){" +
      "#eppcom-win{top:0;left:0;right:0;bottom:0;width:100%;height:100%;max-height:none;border-radius:0;box-shadow:none}" +
      "#eppcom-bubble{bottom:16px;right:16px}" +
      "#eppcom-proactive{bottom:82px;right:16px;max-width:220px}" +
    "}",

    "@supports(padding-top:env(safe-area-inset-top)){@media(max-width:640px){" +
      ".ec-hdr{padding-top:calc(12px + env(safe-area-inset-top))}" +
    "}}",

    /* Header */
    ".ec-hdr{display:flex;align-items:center;gap:10px;padding:12px 14px;border-bottom:1px solid #eee;flex-shrink:0;background:#fff}",
    ".ec-hdr-av{width:36px;height:36px;border-radius:50%;background:CL;display:flex;align-items:center;justify-content:center;flex-shrink:0}",
    ".ec-hdr-av svg{width:20px;height:20px;fill:none;stroke:#fff;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}",
    ".ec-hdr-txt{flex:1;min-width:0}",
    ".ec-hdr-name{font-size:15px;font-weight:600;color:#303235}",
    ".ec-hdr-sub{font-size:12px;color:#71717a;margin-top:1px}",
    ".ec-hdr-x,.ec-hdr-back{background:none;border:none;color:#71717a;font-size:20px;cursor:pointer;padding:4px 6px;line-height:1;flex-shrink:0;-webkit-appearance:none;transition:color .15s}",
    ".ec-hdr-x:hover,.ec-hdr-back:hover{color:#303235}",
    ".ec-hdr-back{display:none;font-size:18px}",
    ".ec-hdr-back.show{display:block}",

    /* Mode area (Begrüßung + Buttons) */
    ".ec-mode-area{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:8px;background:#fff}",
    ".ec-bot-bubble{align-self:flex-start;max-width:84%;background:#F7F8FF;color:#303235;padding:10px 14px;border-radius:4px 18px 18px 4px;font-size:14px;line-height:1.5;white-space:pre-wrap;animation:ec-fade .25s ease}",
    "@keyframes ec-fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}",
    ".ec-choice-row{display:flex;flex-wrap:wrap;gap:6px;animation:ec-fade .25s ease .1s both}",
    ".ec-choice-btn{padding:8px 16px;border-radius:8px;border:1px solid CL;background:#fff;color:CL;cursor:pointer;font-size:13px;font-weight:500;font-family:inherit;transition:all .15s ease;-webkit-appearance:none}",
    ".ec-choice-btn:hover{background:CL;color:#fff}",
    ".ec-choice-btn:active{transform:scale(.97)}",

    /* Voice */
    ".ec-voice-area{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:24px}",
    ".ec-voice-btn{width:72px;height:72px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s ease;font-size:28px;-webkit-appearance:none}",
    ".ec-voice-btn:active{transform:scale(.92)}",
    ".ec-voice-btn.idle{background:#f4f4f5;color:#71717a}",
    ".ec-voice-btn.connecting{background:#fbbf24;color:#fff;animation:ec-pulse 1.5s infinite}",
    ".ec-voice-btn.active{background:#ef4444;color:#fff;animation:ec-pulse 1.5s infinite}",
    "@keyframes ec-pulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.3)}50%{box-shadow:0 0 0 12px rgba(239,68,68,0)}}",
    ".ec-voice-status{font-size:13px;color:#71717a;text-align:center}",
    ".ec-voice-status.connected{color:#059669;font-weight:500}",
    "#ec-voice-audio{display:none}",

    /* Footer */
    ".ec-foot{text-align:center;padding:4px 0 6px;font-size:10px;color:#a1a1aa;background:#fff;flex-shrink:0}",
    ".ec-foot a{color:#a1a1aa;text-decoration:none}",
    ".ec-foot a:hover{text-decoration:underline}"
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

  var chatSVG = '<svg viewBox="0 0 24 24"><path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"/></svg>';

  // ── Bubble ────────────────────────────────────────────────────────────
  var bubble = document.createElement("button");
  bubble.id = "eppcom-bubble";
  bubble.setAttribute("aria-label", "Chat \u00f6ffnen");
  bubble.innerHTML = chatSVG;
  bubble.onclick = function () { openChat(); };
  document.body.appendChild(bubble);

  // ── Proactive ─────────────────────────────────────────────────────────
  var proactive = document.createElement("div");
  proactive.id = "eppcom-proactive";
  proactive.innerHTML = '\uD83D\uDCAC Fragen Sie unseren KI-Assistenten!<button id="eppcom-proactive-x">&times;</button>';
  proactive.onclick = function (e) { if (e.target.id !== "eppcom-proactive-x") openChat(); else proactive.classList.remove("show"); };
  document.body.appendChild(proactive);

  // ── Window (nur für Auswahl + Voice, NICHT für Text-Chat) ─────────────
  var win = document.createElement("div");
  win.id = "eppcom-win";
  win.innerHTML =
    '<div class="ec-hdr">' +
      '<button class="ec-hdr-back" id="ec-back">\u2190</button>' +
      '<div class="ec-hdr-av">' + chatSVG + '</div>' +
      '<div class="ec-hdr-txt"><div class="ec-hdr-name">EPPCOM Assistent</div><div class="ec-hdr-sub" id="ec-hdr-sub">Immer f\u00fcr Sie da</div></div>' +
      '<button class="ec-hdr-x" id="ec-close">\u00D7</button>' +
    '</div>' +
    '<div id="ec-body" style="flex:1;display:flex;flex-direction:column;overflow:hidden;min-height:0">' +
      '<div id="ec-mode-select" class="ec-mode-area">' +
        '<div class="ec-bot-bubble" id="ec-welcome-text"></div>' +
        '<div class="ec-bot-bubble">Wollen Sie mit mir sprechen oder lieber Ihre Tastatur benutzen?</div>' +
        '<div class="ec-choice-row">' +
          '<button class="ec-choice-btn" id="ec-mode-voice">\uD83C\uDF99\uFE0F Sprechen</button>' +
          '<button class="ec-choice-btn" id="ec-mode-text">\u2328\uFE0F Schreiben</button>' +
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
    '<div class="ec-foot">Powered by <a href="https://eppcom.de" target="_blank" rel="noopener">EPPCOM Solutions</a></div>';
  document.body.appendChild(win);

  document.getElementById("ec-welcome-text").textContent = WELCOME;

  // ── Events ────────────────────────────────────────────────────────────
  document.getElementById("ec-close").onclick = closeChat;
  document.getElementById("ec-back").onclick = goBack;
  document.getElementById("ec-mode-text").onclick = function () { switchMode("text"); };
  document.getElementById("ec-mode-voice").onclick = function () { switchMode("voice"); };
  document.getElementById("ec-voice-btn").onclick = toggleVoice;

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
    document.getElementById("ec-mode-select").style.display = "flex";
    document.getElementById("ec-voice-view").style.display = "none";
    document.getElementById("ec-back").classList.remove("show");
    document.getElementById("ec-hdr-sub").textContent = "Immer f\u00fcr Sie da";
  }

  function switchMode(m) {
    mode = m;

    if (m === "text") {
      // ── Unser Fenster schließen, echten Typebot öffnen ──
      closeChat();
      openTypebot();
    } else {
      // ── Voice-Modus im eigenen Fenster ──
      document.getElementById("ec-mode-select").style.display = "none";
      document.getElementById("ec-voice-view").style.display = "flex";
      document.getElementById("ec-back").classList.add("show");
      document.getElementById("ec-hdr-sub").textContent = "Sprach-Chat";
      startVoice();
    }
  }

  // ══════════════════════════════════════════════════════════════════════
  // TYPEBOT INTEGRATION — echter Typebot v2 Chatbot
  // ══════════════════════════════════════════════════════════════════════
  function openTypebot() {
    if (typebotLoaded) {
      // Typebot ist bereits geladen → einfach öffnen
      if (window.Typebot) window.Typebot.open();
      return;
    }

    // Typebot SDK laden
    var s = document.createElement("script");
    s.type = "module";
    s.textContent =
      'import Typebot from "https://cdn.jsdelivr.net/npm/@typebot.io/js@0.3/dist/web.js";' +
      'Typebot.initBubble({' +
        'typebot: "' + TYPEBOT_ID + '",' +
        'apiHost: "' + TYPEBOT_HOST + '",' +
        'theme: {' +
          'button: { backgroundColor: "' + COLOR + '", iconColor: "#FFFFFF", size: "medium" },' +
          'previewMessage: { message: "Wie kann ich Ihnen helfen?", autoShowDelay: 1000 },' +
          'chatWindow: { backgroundColor: "#FFFFFF" }' +
        '}' +
      '});' +
      'window.Typebot = Typebot;' +
      'setTimeout(function() { Typebot.open(); }, 500);';
    document.body.appendChild(s);
    typebotLoaded = true;
  }

  // ══════════════════════════════════════════════════════════════════════
  // VOICE (LiveKit)
  // ══════════════════════════════════════════════════════════════════════
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
