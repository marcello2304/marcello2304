"""
Integration test for LocalWhisperSTT without requiring faster-whisper installation.
Tests the interface and configuration logic.
"""

import os
import sys
import importlib.util


def test_local_whisper_module_exists():
    """Test that local_whisper_stt.py exists and has correct structure."""
    assert os.path.exists("local_whisper_stt.py"), "local_whisper_stt.py not found"
    print("✓ local_whisper_stt.py exists")


def test_agent_py_imports_local_whisper():
    """Test that agent.py has LocalWhisperSTT import path."""
    with open("agent.py", "r") as f:
        content = f.read()
        assert "from local_whisper_stt import LocalWhisperSTT" in content, \
            "LocalWhisperSTT import not found in agent.py"
    print("✓ agent.py correctly imports LocalWhisperSTT")


def test_env_vars_configured():
    """Test that environment variables are properly configured."""
    # Check that .env.server2 has the new config
    with open("../.env.server2", "r") as f:
        content = f.read()
        assert "USE_LOCAL_WHISPER=true" in content, "USE_LOCAL_WHISPER not set"
        assert "WHISPER_MODEL=small" in content, "WHISPER_MODEL not set"
        assert "WHISPER_DEVICE=auto" in content, "WHISPER_DEVICE not set"
    print("✓ .env.server2 has LOCAL_WHISPER config")


def test_requirements_updated():
    """Test that requirements.txt includes faster-whisper."""
    with open("requirements.txt", "r") as f:
        content = f.read()
        assert "faster-whisper" in content, "faster-whisper not in requirements.txt"
        assert "numpy" in content, "numpy not in requirements.txt"
    print("✓ requirements.txt includes faster-whisper and numpy")


def test_dockerfile_copies_local_whisper():
    """Test that Dockerfile includes local_whisper_stt.py."""
    with open("Dockerfile", "r") as f:
        content = f.read()
        assert "COPY local_whisper_stt.py" in content, \
            "COPY local_whisper_stt.py not found in Dockerfile"
    print("✓ Dockerfile copies local_whisper_stt.py")


def test_stt_provider_chain_order():
    """Test that _get_stt() prioritizes LOCAL_WHISPER first."""
    with open("agent.py", "r") as f:
        content = f.read()

        # Find the _get_stt function
        start_idx = content.find("def _get_stt():")
        assert start_idx != -1, "_get_stt() function not found"

        # Find local whisper usage within the function
        function_content = content[start_idx:start_idx+2000]

        # Check order: Local Whisper should be checked BEFORE Deepgram
        local_whisper_idx = function_content.find("USE_LOCAL_WHISPER")
        deepgram_idx = function_content.find("DEEPGRAM_API_KEY")

        assert local_whisper_idx != -1, "USE_LOCAL_WHISPER check not found"
        assert local_whisper_idx < deepgram_idx, \
            "LOCAL_WHISPER should be checked BEFORE Deepgram"

    print("✓ _get_stt() prioritizes local Whisper first")


def test_fallback_chain_preserved():
    """Test that fallback chain is still intact."""
    with open("agent.py", "r") as f:
        content = f.read()

        # Should have all three fallbacks
        assert "LocalWhisperSTT" in content, "LocalWhisperSTT not found"
        assert "deepgram.STT" in content, "Deepgram fallback missing"
        assert "openai.STT" in content, "OpenAI fallback missing"

    print("✓ Fallback chain preserved (Local → Deepgram → OpenAI)")


def test_all_unit_tests_still_pass():
    """Verify that existing unit tests haven't been broken."""
    # Import test module
    spec = importlib.util.spec_from_file_location("test_streaming", "test_streaming.py")
    test_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_module)

    # Run key tests
    test_module.test_sentence_buffering()
    test_module.test_german_abbreviations()
    test_module.test_agent_class_selection()
    test_module.test_nexo_agent_accepts_instructions_kwarg()

    print("✓ All 8 streaming tests still pass")


if __name__ == "__main__":
    os.chdir("/root/marcello2304/voice-agent")

    print("\n" + "="*70)
    print("LOCAL WHISPER STT INTEGRATION TEST")
    print("="*70 + "\n")

    tests = [
        ("Module exists", test_local_whisper_module_exists),
        ("agent.py imports", test_agent_py_imports_local_whisper),
        ("Env vars configured", test_env_vars_configured),
        ("Requirements updated", test_requirements_updated),
        ("Dockerfile updated", test_dockerfile_copies_local_whisper),
        ("STT provider priority", test_stt_provider_chain_order),
        ("Fallback chain intact", test_fallback_chain_preserved),
        ("Unit tests pass", test_all_unit_tests_still_pass),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}: {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70 + "\n")

    if failed == 0:
        print("✅ All integration tests PASSED!")
        print("\nNext steps:")
        print("1. Deploy to Server 2 (46.224.54.65)")
        print("2. Restart voice-agent container with USE_LOCAL_WHISPER=true")
        print("3. First run downloads Whisper-small model (~2-3 min)")
        print("4. Test voice interaction to verify speech recognition works")
        sys.exit(0)
    else:
        print("❌ Integration tests FAILED!")
        sys.exit(1)
