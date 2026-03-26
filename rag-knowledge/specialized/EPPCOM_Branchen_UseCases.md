# EPPCOM Branchen-Spezifische Use Cases

## Gesundheitswesen & Medizin

### Szenario: Arztpraxis mit 3 Ärzten, 2000 Patienten
**Problem**: Anrufe für Terminvereinbarungen blockieren 40% der Arbeitszeit der MFAs (Medizinische Fachangestellte).

**EPPCOM-Lösung**:
- Voicebot am Telefon nimmt Terminwünsche entgegen
- RAG-Zugriff auf Praxis-Kalender (via n8n und Praxissoftware-API)
- Bot prüft Verfügbarkeit, bietet 3 Optionen an
- Bei Zusage: Termin wird direkt in Praxissoftware eingetragen
- Bei Absage: Patient wird auf Warteliste gesetzt

**Technisch**: LiveKit (Telefonie) + Whisper (STT) + qwen2.5:7b (Dialog) + RAG (Praxis-Infos) + n8n (API-Integration) + Cartesia (TTS)

**ROI**: 15h/Woche MFA-Zeit eingespart = ca. 2400 Euro/Monat. Investition: 8000 Euro Setup + 250 Euro/Monat Betrieb.

**Payback**: Nach 3-4 Monaten.

### Szenario: Krankenhaus mit 500 Betten
**Problem**: Patienten und Angehörige rufen wegen Besuchszeiten, Parkplatz-Info, Abteilungs-Standorten an.

**EPPCOM-Lösung**:
- 24/7 Info-Hotline über Voicebot
- RAG-Datenbank mit: Besuchszeiten, Wegbeschreibungen, FAQ zu Aufnahme/Entlassung
- Automatische Weiterleitung zu Notaufnahme bei medizinischen Notfällen

**ROI**: Entlastung der Zentrale um 200+ Anrufe/Tag.

## E-Commerce & Online-Handel

### Szenario: Online-Shop mit 5000 Produkten
**Problem**: 60% der Support-Anfragen sind repetitiv (Versand, Rücksendung, Größen).

**EPPCOM-Lösung**:
- Chatbot auf Website mit RAG-Zugriff auf Produktdatenbank + FAQ
- Automatische Antworten zu: Lieferzeit, Größentabellen, Retourenprozess
- Bei Eskalation: Nahtlose Übergabe an menschlichen Support mit Kontext
- Proaktiver Bot: "Ihr Paket ist unterwegs, Track-Link: ..."

**Technisch**: Typebot (UI) + qwen2.5:7b (NLU) + RAG (Produktdaten + FAQ) + n8n (Shopware/Shopify-Integration)

**ROI**: 40% Reduktion Support-Tickets = 1 FTE eingespart (ca. 36000 Euro/Jahr). Investition: 6000 Euro Setup + 200 Euro/Monat.

**Payback**: Nach 5-6 Monaten.

### Szenario: Fashion E-Commerce mit internationalen Kunden
**Problem**: Größentabellen variieren (US/EU/UK), viele Rückfragen vor Kauf.

**EPPCOM-Lösung**:
- Multilingualer Chatbot (DE/EN/FR)
- RAG mit Größentabellen, Material-Pflegehinweisen, Style-Guides
- Produktempfehlungen basierend auf Körpermaßen

**ROI**: 25% weniger Retouren durch bessere Beratung = 15000 Euro/Jahr bei 100k Euro Retourenkosten.

## Industrie & B2B

### Szenario: Maschinen-Hersteller mit 200 Servicetechnikern
**Problem**: Techniker rufen bei Störungen in der Zentrale an - Wartezeiten, kein 24/7-Support.

**EPPCOM-Lösung**:
- Voicebot als First-Level-Diagnose-Hotline
- RAG-Zugriff auf Wartungshandbücher, Fehlercode-Datenbanken
- Bot führt Techniker durch Troubleshooting-Schritte
- Bei komplexen Fällen: Ticket erstellen + Experte wird informiert

**Technisch**: LiveKit (Telefonie) + Whisper + qwen2.5:7b + RAG (Handbücher als PDF) + n8n (Ticket-System)

**ROI**: 24/7 Verfügbarkeit ohne Nachtschicht-Kosten. 30% schnellere Problemlösung. Investition: 12000 Euro Setup + 300 Euro/Monat.

**Effekt**: Downtime-Reduktion um durchschnittlich 2h pro Störfall - massive Kundenzufriedenheits-Steigerung.

### Szenario: Logistik-Unternehmen mit Fuhrpark
**Problem**: Fahrer rufen bei Routenfragen, Lieferadress-Problemen, Fahrzeug-Störungen an.

**EPPCOM-Lösung**:
- Voicebot für Fahrer (hands-free während Fahrt)
- RAG mit: Routenplänen, Kunden-Adressen, Fahrzeug-Wartungsinfos
- Integration mit Telematics-System für Echtzeit-Fahrzeugdaten

**ROI**: 50% weniger Support-Anrufe = 1 Dispatcher-FTE eingespart.

## Immobilien & Hausverwaltung

### Szenario: Hausverwaltung mit 500 Wohneinheiten
**Problem**: Mieter rufen wegen Schlüsselverlust, Heizungsausfall, Müllabfuhr-Terminen an.

**EPPCOM-Lösung**:
- 24/7 Voicebot für Standard-Anfragen
- RAG mit: Hausordnung, Notdienst-Nummern, Müllabfuhr-Kalender
- Automatische Ticket-Erstellung für Reparatur-Anfragen

**ROI**: 30% Reduktion eingehender Anrufe, schnellere Notfall-Reaktion.

### Szenario: Makler-Büro mit 200 aktiven Immobilien
**Problem**: Interessenten rufen wegen Besichtigungsterminen, Exposés, Verfügbarkeit an.

**EPPCOM-Lösung**:
- Chatbot auf Website und WhatsApp
- RAG mit aktuellen Immobilien-Exposés, Grundrissen, Lagebeschreibungen
- Automatische Terminvereinbarung für Besichtigungen
- Lead-Qualifizierung: Budget, Zeitrahmen, Präferenzen erfassen

**ROI**: 3x mehr qualifizierte Leads bei gleichem Personalaufwand.

## Finanzdienstleistungen

### Szenario: Bank mit 50000 Kunden
**Problem**: 70% der Hotline-Anrufe sind einfache Fragen (Kontostand, Karten-Sperrung, Überweisungslimit).

**EPPCOM-Lösung**:
- Voicebot mit starker Authentifizierung (2FA)
- RAG mit: Produkt-Infos (Kredite, Girokonten), Sicherheits-Guides
- Eskalation zu menschlichem Berater bei komplexen Finanz-Themen

**Compliance**: Vollständig DSGVO-konform, keine Daten verlassen Deutschland.

**ROI**: 60% Automatisierungsrate = 3-4 Call-Center-FTEs eingespart (ca. 150000 Euro/Jahr).

### Szenario: Versicherungsmakler mit 2000 Kunden
**Problem**: Kunden fragen regelmäßig nach Deckungssummen, Kündigungsfristen, Schadensmeldungs-Prozessen.

**EPPCOM-Lösung**:
- Chatbot mit RAG-Zugriff auf Versicherungsbedingungen
- Automatische Schadensmeldung mit Foto-Upload
- Proaktive Erinnerungen: Vertragsverlängerungen, fehlende Unterlagen

**ROI**: 40% weniger Rückfragen, 20% schnellere Schadenbearbeitung.

## Öffentliche Verwaltung & Verbände

### Szenario: Stadtverwaltung mit 50000 Einwohnern
**Problem**: Bürger rufen wegen Öffnungszeiten, Antragsformularen, Zuständigkeiten an.

**EPPCOM-Lösung**:
- 24/7 Bürger-Hotline mit Voicebot
- RAG mit: Dienstleistungskatalog, Formulare, Zuständigkeits-Matrix
- Mehrsprachig (DE/EN/TR/AR) für diverse Bevölkerung

**ROI**: 50% Entlastung des Bürgerservice-Telefons.

### Szenario: Politischer Verband mit 5000 Mitgliedern
**Problem**: Mitglieder fragen nach Positionen, Veranstaltungen, Mitgliedsbeiträgen.

**EPPCOM-Lösung**:
- Chatbot auf Website mit RAG-Zugriff auf Positionspapiere, Satzung, Veranstaltungskalender
- Automatische Mitglieder-Onboarding-Unterstützung
- FAQ zu Beiträgen, Kündigungen, Engagement-Möglichkeiten

**ROI**: Entlastung der Geschäftsstelle um 20h/Woche.
