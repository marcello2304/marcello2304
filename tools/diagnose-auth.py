#!/usr/bin/env python3
"""
Diagnose-Script für Login + E-Mail Probleme.
Ausführen IM Docker-Container:
  docker exec -it eppcom-admin-ui python /app/tools/diagnose-auth.py

Oder lokal mit DB-Zugriff:
  python tools/diagnose-auth.py
"""
import os
import sys
import asyncio
import bcrypt
import asyncpg
import secrets

DATABASE_URL = os.getenv("DATABASE_URL", "")

async def main():
    if not DATABASE_URL:
        print("FEHLER: DATABASE_URL nicht gesetzt")
        sys.exit(1)

    conn = await asyncpg.connect(DATABASE_URL)
    print("✓ Datenbankverbindung erfolgreich\n")

    # ── 1. User-Check ────────────────────────────────────────────────────
    print("=" * 55)
    print("1. USER-CHECK")
    print("=" * 55)

    users = await conn.fetch(
        "SELECT id, email, display_name, role, is_active, "
        "LEFT(password_hash, 20) AS hash_prefix "
        "FROM public.users ORDER BY email"
    )

    if not users:
        print("⚠  Keine User in der Datenbank!")
    else:
        print(f"{'Email':<35} {'Aktiv':<7} {'Rolle':<12} {'Hash-Prefix'}")
        print("-" * 75)
        for u in users:
            aktiv = "✓ JA" if u["is_active"] else "✗ NEIN"
            print(f"{u['email']:<35} {aktiv:<7} {u['role'] or '?':<12} {u['hash_prefix']}...")

    print()

    # ── 2. Passwort direkt zurücksetzen ──────────────────────────────────
    print("=" * 55)
    print("2. PASSWORT ZURÜCKSETZEN")
    print("=" * 55)

    target_email = input("E-Mail des Nutzers (Enter = überspringen): ").strip().lower()
    if target_email:
        user = await conn.fetchrow(
            "SELECT id, email, is_active FROM public.users WHERE email=$1", target_email
        )
        if not user:
            print(f"✗ Kein User mit E-Mail '{target_email}' gefunden!")
        else:
            new_pw = input("Neues Passwort (Enter = zufällig generieren): ").strip()
            if not new_pw:
                new_pw = secrets.token_urlsafe(12)

            pw_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
            await conn.execute(
                "UPDATE public.users SET password_hash=$1, is_active=true WHERE id=$2",
                pw_hash, user["id"]
            )
            print(f"\n✓ Passwort für '{target_email}' erfolgreich gesetzt!")
            print(f"  Neues Passwort: {new_pw}")
            print(f"  Account aktiv:  JA")
            print()
            print("→ Jetzt kannst du dich unter appdb.eppcom.de einloggen.")

    print()

    # ── 3. SMTP-Test ─────────────────────────────────────────────────────
    print("=" * 55)
    print("3. SMTP-TEST")
    print("=" * 55)

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    print(f"SMTP_HOST:  {smtp_host or '✗ NICHT GESETZT'}")
    print(f"SMTP_PORT:  {smtp_port}")
    print(f"SMTP_USER:  {smtp_user or '✗ NICHT GESETZT'}")
    print(f"SMTP_PASS:  {'✓ gesetzt' if smtp_pass else '✗ NICHT GESETZT'}")
    print(f"SMTP_FROM:  {smtp_from or '✗ NICHT GESETZT'}")
    print()

    if not smtp_host or not smtp_user or not smtp_pass:
        print("✗ SMTP ist nicht vollständig konfiguriert!")
        print("  Setze in admin-ui/.env:")
        print("    SMTP_HOST=smtp.ionos.de")
        print("    SMTP_PORT=587")
        print("    SMTP_USER=eppler@eppcom.de")
        print("    SMTP_PASSWORD=<dein-ionos-passwort>")
        print("    SMTP_FROM=eppler@eppcom.de")
    else:
        do_test = input(f"Test-E-Mail senden an '{smtp_user}'? (j/n): ").strip().lower()
        if do_test == "j":
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            try:
                msg = MIMEMultipart("alternative")
                msg["From"] = f"EPPCOM Diagnose <{smtp_from}>"
                msg["To"]   = smtp_user
                msg["Subject"] = "EPPCOM SMTP-Test"
                msg.attach(MIMEText("<p>SMTP funktioniert!</p>", "html", "utf-8"))

                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(smtp_from, smtp_user, msg.as_string())
                print(f"✓ Test-E-Mail erfolgreich gesendet an {smtp_user}!")
            except Exception as e:
                print(f"✗ SMTP-Fehler: {e}")
                print()
                print("Mögliche Ursachen:")
                print("  - Falsches Passwort")
                print("  - IONOS: App-Passwort nötig? → IONOS-Dashboard → E-Mail → Einstellungen")
                print("  - Port blockiert? Versuche SMTP_PORT=465 mit SSL")

    await conn.close()
    print("\nFertig.")

asyncio.run(main())
