/* EPPCOM Jitsi Custom Config */

// Prejoin-Seite aktivieren (Name, Kamera, Mikro)
config.prejoinConfig = {
    enabled: true,
    hideExtraJoinButtons: ['no-audio', 'by-phone']
};

// Auto-Redirect: Sofort zur Meeting-Auth Seite, OHNE Jitsis eingebauten "Sind Sie der Host?"-Dialog
config.tokenAuthUrlAutoRedirect = true;

// Virtuelle Hintergründe aktivieren
config.disableVirtualBackground = false;
config.backgroundAlpha = 0.5;

// Allgemeine Einstellungen
config.disableDeepLinking = true;
config.enableWelcomePage = false;
config.enableClosePage = false;
config.defaultLanguage = 'de';
