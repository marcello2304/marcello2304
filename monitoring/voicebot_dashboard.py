#!/usr/bin/env python3
"""
EPPCOM Voicebot Performance Dashboard
Zeigt Live-Metriken aus der letzten 24h

Usage: python3 voicebot_dashboard.py
  Env: DATABASE_URL=postgresql://user:pass@host:5432/db
"""

import asyncio
import asyncpg
import os
from datetime import datetime


async def main():
    db_url = os.environ.get("DATABASE_URL", "postgresql://appuser:MXeuHHCnuYDCa88ly3sEGl6agCK8f5UUSdKES8cD@postgres-rag:5432/app_db")
    db = await asyncpg.connect(db_url)

    print("\n" + "=" * 80)
    print("EPPCOM VOICEBOT PERFORMANCE DASHBOARD".center(80))
    print(f"Stand: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(80))
    print("=" * 80)

    # Performance Stats
    stats = await db.fetch("""
        SELECT
            step,
            COUNT(*) as total_calls,
            ROUND(AVG(duration_ms)) as avg_ms,
            ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms)) as median_ms,
            ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)) as p95_ms,
            MIN(duration_ms) as min_ms,
            MAX(duration_ms) as max_ms
        FROM voicebot_metrics
        WHERE timestamp > NOW() - INTERVAL '24 hours'
        GROUP BY step
        ORDER BY
            CASE step
                WHEN 'total' THEN 1
                WHEN 'llm' THEN 2
                WHEN 'rag' THEN 3
                WHEN 'embedding' THEN 4
                WHEN 'tts' THEN 5
            END
    """)

    print("\nLATENCY STATISTIKEN (24h)\n")
    if stats:
        print(f"{'Step':<12} {'Calls':>8} {'Avg':>8} {'Median':>8} {'P95':>8} {'Min':>8} {'Max':>8}")
        print("-" * 68)
        for row in stats:
            print(f"{row['step']:<12} {row['total_calls']:>8} {row['avg_ms']:>7}ms {row['median_ms']:>7}ms {row['p95_ms']:>7}ms {row['min_ms']:>7}ms {row['max_ms']:>7}ms")
    else:
        print("Noch keine Metriken vorhanden.")

    # Slow Queries
    slow = await db.fetch("""
        SELECT session_id, user_query, total_duration_ms, timestamp
        FROM voicebot_slow_queries
        WHERE timestamp > NOW() - INTERVAL '24 hours'
        ORDER BY timestamp DESC
        LIMIT 5
    """)

    print("\n\nSLOW QUERIES (>3s, letzte 5)\n")
    if slow:
        for row in slow:
            ts = row['timestamp'].strftime('%H:%M:%S')
            query = (row['user_query'] or '')[:50]
            print(f"[{ts}] {row['total_duration_ms']}ms - {query}...")
    else:
        print("Keine Slow Queries in den letzten 24h")

    # Hourly Volume
    hourly = await db.fetch("""
        SELECT
            DATE_TRUNC('hour', timestamp) as hour,
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as total_calls
        FROM voicebot_metrics
        WHERE timestamp > NOW() - INTERVAL '24 hours'
        GROUP BY hour
        ORDER BY hour DESC
        LIMIT 12
    """)

    print("\n\nSTUENDLICHES VOLUMEN (letzte 12h)\n")
    if hourly:
        print(f"{'Stunde':<20} {'Sessions':>10} {'Calls':>10}")
        print("-" * 42)
        for row in hourly:
            print(f"{row['hour'].strftime('%Y-%m-%d %H:00'):<20} {row['sessions']:>10} {row['total_calls']:>10}")
    else:
        print("Noch keine Daten.")

    print("\n" + "=" * 80 + "\n")
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
