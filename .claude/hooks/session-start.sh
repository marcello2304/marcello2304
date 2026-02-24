#!/bin/bash
# .claude/hooks/session-start.sh
# Wird automatisch beim Start jeder Claude Code Session ausgeführt.
# Bereitet die Umgebung vor: Tools prüfen, Scripts ausführbar machen,
# .env erzeugen falls fehlend, Status ausgeben.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$PROJECT_DIR"

# ── Alle Scripts ausführbar machen ──────────────────────────────────────
chmod +x scripts/*.sh 2>/dev/null || true
chmod +x setup.sh 2>/dev/null || true

# ── .env aus Template erzeugen falls noch nicht vorhanden ───────────────
if [ ! -f ".env" ]; then
    cp coolify/env-templates/server1.env.example .env
    echo "[session-start] .env aus Template erstellt — bitte ausfüllen"
fi

# ── .gitignore sicherstellen (kein Secrets-Commit) ───────────────────────
if ! grep -q "^\.env$" .gitignore 2>/dev/null; then
    echo ".env" >> .gitignore
    echo ".env.local" >> .gitignore
    echo "diagnose-output.txt" >> .gitignore
    echo "*.dump" >> .gitignore
    echo "/opt/backups/" >> .gitignore
fi

# ── Basis-Tools prüfen (nur in Remote-Umgebung installieren) ─────────────
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
    # In Claude Code Web: Tools nachinstallieren falls nötig
    if ! command -v jq &>/dev/null; then
        apt-get install -q -y jq 2>/dev/null || true
    fi
    if ! command -v aws &>/dev/null; then
        pip3 install -q awscli 2>/dev/null || true
    fi
fi

# ── Umgebungsvariablen für die Session setzen ────────────────────────────
if [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -f ".env" ]; then
    # Nur Nicht-Secret-Variablen für die Session exportieren
    grep -E "^(DOMAIN|TZ|S3_REGION|S3_ENDPOINT|S3_BUCKET|OLLAMA_BASE_URL)=" .env \
        2>/dev/null >> "$CLAUDE_ENV_FILE" || true
fi

# ── Status-Ausgabe für Claude Code ──────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  Hetzner RAG Platform — Session bereit"
echo "════════════════════════════════════════════════════════"
echo ""
echo "  Verfügbare Slash-Commands:"
echo "    /setup       → Vollständiges Setup starten"
echo "    /diagnose    → Domain-Diagnose ausführen"
echo "    /status      → Stack-Status anzeigen"
echo "    /new-tenant  → Neuen Kunden anlegen"
echo "    /backup      → Backup ausführen"
echo "    /migrate     → SQL-Migrationen ausführen"
echo "    /logs        → Container-Logs anzeigen"
echo ""

# Container-Status (falls Docker verfügbar)
if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
    RUNNING=$(docker ps --format "{{.Names}}" 2>/dev/null | grep -E "postgres|n8n|typebot|traefik|coolify" | tr '\n' ' ' || echo "keine RAG-Container gefunden")
    echo "  Laufende Container: $RUNNING"
    echo ""
fi

# .env Status
if grep -q "HIER\|AENDERN" .env 2>/dev/null; then
    echo "  ⚠  .env enthält noch Platzhalter → /setup ausführen"
else
    echo "  ✓  .env konfiguriert"
fi

echo ""
echo "  → CLAUDE.md für vollständigen Kontext lesen"
echo "════════════════════════════════════════════════════════"
echo ""
