<?php
/**
 * EPPCOM Voicebot – Einbindung auf www.eppcom.de/test.php
 * Dieses File auf dem Website-Server hochladen.
 * Das eigentliche Widget läuft auf appdb.eppcom.de.
 */
?>
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EPPCOM Voicebot – Test</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f0f4ff;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
            gap: 24px;
        }
        h1 {
            font-size: 22px;
            color: #1e3a8a;
            text-align: center;
        }
        p {
            color: #555;
            text-align: center;
            font-size: 14px;
            max-width: 400px;
        }
        .widget-container {
            width: 340px;
            height: 440px;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 12px 48px rgba(30, 58, 138, 0.2);
        }
        iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
        .back {
            font-size: 13px;
            color: #888;
        }
        .back a { color: #1e3a8a; text-decoration: none; }
    </style>
</head>
<body>
    <h1>Nexo – KI-Assistent von EPPCOM</h1>
    <p>Teste unseren KI-Sprachassistenten. Klicke auf das Mikrofon und stelle eine Frage.</p>

    <div class="widget-container">
        <iframe
            src="https://appdb.eppcom.de/voice-widget"
            allow="microphone"
            title="EPPCOM Voicebot"
        ></iframe>
    </div>

    <p class="back"><a href="https://www.eppcom.de">&larr; Zurück zur Website</a></p>
</body>
</html>
