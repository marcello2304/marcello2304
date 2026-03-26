#!/usr/bin/env python3
"""
A/B Vergleich: qwen3:1.7b vs qwen2.5:7b-eppcom
Testet Response-Qualitaet und Latency
"""

import requests
import time
import json

OLLAMA_URL = "http://46.224.54.65:11434/api/generate"

TEST_PROMPTS = [
    {
        "name": "Self-Hosting Erklaerung",
        "prompt": "Erklaere in 2-3 Saetzen: Warum ist Self-Hosting bei EPPCOM wichtig?"
    },
    {
        "name": "RAG vs. Standard Chatbot",
        "prompt": "Was ist der Unterschied zwischen einem RAG-Chatbot und einem normalen Chatbot?"
    },
    {
        "name": "Branchen Use-Case",
        "prompt": "Nenne ein Beispiel, wie eine Arztpraxis von EPPCOM profitieren kann."
    },
    {
        "name": "ROI Erklaerung",
        "prompt": "Wie schnell amortisiert sich eine EPPCOM-Loesung typischerweise?"
    }
]


def test_model(model_name, prompt):
    start = time.time()
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 150
            }
        }, timeout=60)
        duration = (time.time() - start) * 1000
        response_text = resp.json().get("response", "")
        return {
            "duration_ms": duration,
            "response": response_text,
            "token_count": len(response_text.split()),
            "success": True
        }
    except Exception as e:
        return {
            "duration_ms": (time.time() - start) * 1000,
            "response": "",
            "token_count": 0,
            "success": False,
            "error": str(e)
        }


def score_response(response):
    score = 5
    word_count = len(response.split())
    if 20 <= word_count <= 80:
        score += 2
    elif word_count < 10 or word_count > 150:
        score -= 2
    keywords = ['eppcom', 'dsgvo', 'self-hosting', 'rag', 'workflow',
                'automatisierung', 'n8n', 'typebot', 'roi', 'daten', 'server']
    keyword_count = sum(1 for kw in keywords if kw.lower() in response.lower())
    score += min(keyword_count, 3)
    words = response.lower().split()
    unique_ratio = len(set(words)) / max(len(words), 1)
    if unique_ratio < 0.6:
        score -= 2
    return max(0, min(10, score))


def main():
    print("\n" + "=" * 80)
    print("EPPCOM MODEL A/B COMPARISON".center(80))
    print("qwen3:1.7b vs qwen2.5:7b-eppcom".center(80))
    print("=" * 80)

    overall_old_time = 0
    overall_new_time = 0
    overall_old_quality = 0
    overall_new_quality = 0

    for test in TEST_PROMPTS:
        print(f"\nTesting: {test['name']}...")

        old_result = test_model("qwen3:1.7b", test['prompt'])
        time.sleep(2)
        new_result = test_model("qwen2.5:7b-eppcom", test['prompt'])
        time.sleep(2)

        old_score = score_response(old_result['response'])
        new_score = score_response(new_result['response'])

        print(f"\n{'=' * 80}")
        print(f"TEST: {test['name']}")
        print(f"{'=' * 80}")
        print(f"\n{'METRIK':<25} {'qwen3:1.7b':<25} {'qwen2.5:7b-eppcom':<25}")
        print("-" * 80)
        print(f"{'Latency':<25} {old_result['duration_ms']:.0f}ms{'':<18} {new_result['duration_ms']:.0f}ms")
        print(f"{'Length':<25} {old_result['token_count']} words{'':<16} {new_result['token_count']} words")
        print(f"{'Quality (0-10)':<25} {old_score:<25} {new_score:<25}")
        print(f"\nOLD: {old_result['response'][:200]}")
        print(f"\nNEW: {new_result['response'][:200]}")

        overall_old_time += old_result['duration_ms']
        overall_new_time += new_result['duration_ms']
        overall_old_quality += old_score
        overall_new_quality += new_score

    num_tests = len(TEST_PROMPTS)
    avg_old_time = overall_old_time / num_tests
    avg_new_time = overall_new_time / num_tests
    avg_old_quality = overall_old_quality / num_tests
    avg_new_quality = overall_new_quality / num_tests

    print(f"\n{'=' * 80}")
    print("OVERALL SUMMARY".center(80))
    print(f"{'=' * 80}")
    print(f"\n{'METRIK':<30} {'qwen3:1.7b':<20} {'qwen2.5:7b-eppcom':<20}")
    print("-" * 70)
    print(f"{'Avg Latency':<30} {avg_old_time:.0f}ms{'':<14} {avg_new_time:.0f}ms")
    print(f"{'Avg Quality':<30} {avg_old_quality:.1f}/10{'':<13} {avg_new_quality:.1f}/10")

    if avg_new_time > 0:
        print(f"{'Speedup':<30} {'1.0x':<20} {avg_old_time/avg_new_time:.2f}x")

    if avg_new_quality > avg_old_quality:
        print("\nEMPFEHLUNG: Migriere zu qwen2.5:7b-eppcom - bessere Qualitaet!")
    elif avg_new_time < avg_old_time:
        print("\nEMPFEHLUNG: qwen2.5:7b-eppcom ist schneller, Qualitaet aehnlich")
    else:
        print("\nWARNUNG: Keine klaren Vorteile - weitere Tests noetig")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
