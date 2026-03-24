/**
 * EPPCOM Chat + Voice Widget
 * Lädt Typebot sofort als Hauptchatbot + optionaler Voice-Button
 *
 * Einbindung (vor </body>):
 *   <script src="https://appdb.eppcom.de/widget/chat-widget.js"
 *           data-typebot-id="eppcom-chatbot-v2"
 *           data-typebot-host="https://bot.eppcom.de"
 *           data-voice-token-url="https://appdb.eppcom.de/api/public/voice-token"
 *           data-livekit-url="wss://voice.eppcom.de"
 *           data-color="#0042DA"
 *           data-auto-open="true"
 *           defer></script>
 */
(function () {
  "use strict";

  var script = document.currentScript || document.querySelector("script[data-typebot-id]");
  var TYPEBOT_ID = (script && script.getAttribute("data-typebot-id")) || "eppcom-chatbot-v2";
  var TYPEBOT_HOST = (script && script.getAttribute("data-typebot-host")) || "https://bot.eppcom.de";
  var VOICE_TOKEN_URL = (script && script.getAttribute("data-voice-token-url")) || "https://appdb.eppcom.de/api/public/voice-token";
  var LIVEKIT_URL = (script && script.getAttribute("data-livekit-url")) || "wss://appdb.eppcom.de:7443";
  var COLOR = (script && (script.getAttribute("data-color") || script.getAttribute("data-accent"))) || "#0042DA";
  var AUTO_OPEN = (script && script.getAttribute("data-auto-open")) === "true";

  var SESSION = "web_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
  var voiceRoom = null;
  var voiceConnecting = false;
  var voiceOpen = false;

  // ═══════════════════════════════════════════════════════════════════════
  // 1) TYPEBOT — sofort laden und initialisieren
  // ═══════════════════════════════════════════════════════════════════════
  var typebotScript = document.createElement("script");
  typebotScript.type = "module";
  typebotScript.textContent =
    'import Typebot from "https://cdn.jsdelivr.net/npm/@typebot.io/js@0.3/dist/web.js";' +
    'Typebot.initBubble({' +
      'typebot: "' + TYPEBOT_ID + '",' +
      'apiHost: "' + TYPEBOT_HOST + '",' +
      'theme: {' +
        'button: { backgroundColor: "' + COLOR + '", iconColor: "#FFFFFF", size: "medium" },' +
        'previewMessage: { message: "\uD83D\uDCAC Hallo! Ich bin Nexo \u2014 wie kann ich helfen?", autoShowDelay: 3000 },' +
        'chatWindow: { backgroundColor: "#FFFFFF" }' +
      '}' +
    '});' +
    'window._Typebot = Typebot;' +
    (AUTO_OPEN ? 'setTimeout(function() { Typebot.open(); }, 1500);' : '');
  document.body.appendChild(typebotScript);

  // ═══════════════════════════════════════════════════════════════════════
  // 2) VOICE BUTTON — kleiner Mikrofon-Button neben der Typebot-Bubble
  // ═══════════════════════════════════════════════════════════════════════
  var voiceCSS = document.createElement("style");
  voiceCSS.textContent = [
    "#eppcom-voice-fab{position:fixed;bottom:20px;right:80px;z-index:42424243;width:44px;height:44px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:20px;transition:all .2s;-webkit-appearance:none;box-shadow:0 2px 8px rgba(0,0,0,.15)}",
    "#eppcom-voice-fab.idle{background:#fff;color:#71717a}",
    "#eppcom-voice-fab.idle:hover{background:#f4f4f5;transform:scale(1.1)}",
    "#eppcom-voice-fab.connecting{background:#fbbf24;color:#fff;animation:ev-pulse 1.5s infinite}",
    "#eppcom-voice-fab.active{background:#ef4444;color:#fff;animation:ev-pulse 1.5s infinite}",
    "@keyframes ev-pulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.3)}50%{box-shadow:0 0 0 10px rgba(239,68,68,0)}}",
    "#eppcom-voice-fab:active{transform:scale(.9)}",

    /* Voice Overlay */
    "#eppcom-voice-overlay{position:fixed;bottom:88px;right:20px;z-index:42424244;width:320px;background:#fff;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.12),0 0 0 1px rgba(0,0,0,.05);display:none;flex-direction:column;align-items:center;padding:24px;gap:14px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;opacity:0;transform:translateY(12px);transition:opacity .2s,transform .2s}",
    "#eppcom-voice-overlay.open{display:flex}",
    "#eppcom-voice-overlay.visible{opacity:1;transform:translateY(0)}",
    "#eppcom-voice-overlay h3{font-size:15px;font-weight:600;color:#303235;margin:0}",

    ".ev-mic-btn{width:64px;height:64px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:26px;transition:all .2s;-webkit-appearance:none}",
    ".ev-mic-btn.idle{background:#f4f4f5;color:#71717a}",
    ".ev-mic-btn.connecting{background:#fbbf24;color:#fff;animation:ev-pulse 1.5s infinite}",
    ".ev-mic-btn.active{background:#ef4444;color:#fff;animation:ev-pulse 1.5s infinite}",
    ".ev-mic-btn:active{transform:scale(.9)}",
    ".ev-status{font-size:13px;color:#71717a;text-align:center}",
    ".ev-status.connected{color:#059669;font-weight:500}",
    ".ev-close{background:none;border:none;position:absolute;top:8px;right:10px;font-size:18px;color:#999;cursor:pointer;padding:4px;line-height:1}",
    ".ev-close:hover{color:#333}",
    "#ev-audio{display:none}",

    /* Mobile */
    "@media(max-width:640px){" +
      "#eppcom-voice-fab{bottom:16px;right:72px}" +
      "#eppcom-voice-overlay{right:8px;left:8px;width:auto;bottom:76px}" +
    "}"
  ].join("\n");
  document.head.appendChild(voiceCSS);

  // Voice FAB (Floating Action Button)
  var voiceFab = document.createElement("button");
  voiceFab.id = "eppcom-voice-fab";
  voiceFab.className = "idle";
  voiceFab.title = "Sprach-Assistent";
  voiceFab.innerHTML = "\uD83C\uDF99\uFE0F";
  voiceFab.onclick = function () { toggleVoiceOverlay(); };
  document.body.appendChild(voiceFab);

  // Voice Overlay
  var voiceOverlay = document.createElement("div");
  voiceOverlay.id = "eppcom-voice-overlay";
  voiceOverlay.innerHTML =
    '<button class="ev-close" id="ev-close">\u00D7</button>' +
    '<h3>Nexo Sprach-Assistent</h3>' +
    '<button class="ev-mic-btn idle" id="ev-mic-btn">\uD83C\uDF99\uFE0F</button>' +
    '<div class="ev-status" id="ev-status">Antippen zum Starten</div>' +
    '<div id="ev-audio"></div>';
  document.body.appendChild(voiceOverlay);

  document.getElementById("ev-close").onclick = function () { closeVoiceOverlay(); };
  document.getElementById("ev-mic-btn").onclick = function () { toggleVoice(); };

  function toggleVoiceOverlay() {
    if (voiceOpen) {
      closeVoiceOverlay();
    } else {
      voiceOpen = true;
      voiceOverlay.classList.add("open");
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { voiceOverlay.classList.add("visible"); });
      });
      // Auto-start voice connection
      if (!voiceRoom && !voiceConnecting) startVoice();
    }
  }

  function closeVoiceOverlay() {
    voiceOverlay.classList.remove("visible");
    setTimeout(function () {
      voiceOpen = false;
      voiceOverlay.classList.remove("open");
    }, 200);
    if (voiceRoom) stopVoice();
  }

  // ═══════════════════════════════════════════════════════════════════════
  // 3) VOICE ENGINE (LiveKit)
  // ═══════════════════════════════════════════════════════════════════════
  function setVoiceState(state, statusText) {
    var fab = document.getElementById("eppcom-voice-fab");
    var btn = document.getElementById("ev-mic-btn");
    var st = document.getElementById("ev-status");
    fab.className = state;
    btn.className = "ev-mic-btn " + state;
    st.textContent = statusText;
    st.className = "ev-status" + (state === "active" ? " connected" : "");
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
          document.getElementById("ev-audio").appendChild(el);
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
    var ac = document.getElementById("ev-audio");
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
