#!/bin/bash
echo "=== Voicebot Webhook Test ==="

WEBHOOK_URL="${WEBHOOK_URL:-https://workflows.eppcom.de/webhook/voicebot-input}"

# Test 1: Einfache Frage
echo -e "\n[Test 1] Frage: Was macht EPPCOM?"
curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Was macht EPPCOM?",
    "session_id": "test-001",
    "tenant_slug": "eppcom"
  }' | python3 -m json.tool 2>/dev/null || echo "(raw output above)"

# Test 2: Self-Hosting Frage
echo -e "\n[Test 2] Frage: Warum Self-Hosting?"
curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Warum sollte ich Self-Hosting wählen statt Cloud?",
    "session_id": "test-002",
    "tenant_slug": "eppcom"
  }' | python3 -m json.tool 2>/dev/null || echo "(raw output above)"

# Test 3: RAG-Technologie Frage
echo -e "\n[Test 3] Frage: Wie funktioniert RAG?"
curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Kannst du mir erklären wie die RAG-Technologie funktioniert?",
    "session_id": "test-003",
    "tenant_slug": "eppcom"
  }' | python3 -m json.tool 2>/dev/null || echo "(raw output above)"

echo -e "\n=== Tests abgeschlossen ==="
