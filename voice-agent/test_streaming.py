import os
import re
import pytest

from constants import SENTENCE_PATTERN, MAX_SENTENCE_LENGTH, TRUNCATION_SUFFIX

def buffer_tokens_until_sentence(text_stream):
    """Pure function: buffer tokens until sentence boundary.

    Args:
        text_stream: List of text chunks (simulating ChatChunk.text)

    Returns:
        List of complete sentences
    """
    buffer = ""
    results = []

    for text_chunk in text_stream:
        buffer += text_chunk

        while re.search(SENTENCE_PATTERN, buffer):
            sentences = re.split(SENTENCE_PATTERN, buffer, maxsplit=1)
            sentence = sentences[0].strip()
            buffer = sentences[1] if len(sentences) > 1 else ""

            # Handle oversized sentences
            if len(sentence) > MAX_SENTENCE_LENGTH:
                sentence = (
                    sentence[:MAX_SENTENCE_LENGTH - len(TRUNCATION_SUFFIX)]
                    + TRUNCATION_SUFFIX
                )

            if sentence:
                results.append(sentence)

    # Yield remaining text
    if buffer.strip():
        final_text = buffer.strip()
        if len(final_text) > MAX_SENTENCE_LENGTH:
            final_text = (
                final_text[:MAX_SENTENCE_LENGTH - len(TRUNCATION_SUFFIX)]
                + TRUNCATION_SUFFIX
            )
        results.append(final_text)

    return results


def test_sentence_buffering():
    """Test that tokens buffer correctly until sentence boundary."""
    text_chunks = ["Hello ", "world. ", "This is ", "a test."]
    result = buffer_tokens_until_sentence(text_chunks)

    expected = ["Hello world.", "This is a test."]
    assert result == expected, f"Expected {expected}, got {result}"


def test_oversized_sentence_truncation():
    """Test that oversized sentences are truncated."""
    long_sentence = "A" * 300 + ". "
    text_chunks = [long_sentence, "Next sentence."]
    result = buffer_tokens_until_sentence(text_chunks)

    # First chunk should be truncated to MAX_SENTENCE_LENGTH
    assert len(result[0]) <= MAX_SENTENCE_LENGTH
    assert result[0].endswith("...")


def test_german_abbreviations():
    """Test sentence boundaries with German text."""
    text_chunks = ["Herr Mueller arbeitet. ", "Das ist ", "wichtig."]
    result = buffer_tokens_until_sentence(text_chunks)

    # Should detect 2 sentences
    assert len(result) == 2
    assert "Herr Mueller arbeitet." in result[0]
    assert "Das ist wichtig." in result[1]


def test_exclamation_and_question_boundaries():
    """Test sentence boundaries with exclamation and question marks."""
    result_excl = buffer_tokens_until_sentence(["Fantastisch! ", "Das freut mich."])
    assert result_excl == ["Fantastisch!", "Das freut mich."]

    result_ques = buffer_tokens_until_sentence(["Wie geht es? ", "Gut danke."])
    assert result_ques == ["Wie geht es?", "Gut danke."]


def test_lowercase_continuation_no_split():
    """Test that lowercase continuation after period doesn't split."""
    chunks = ["z.B. das ist klar. ", "Wirklich wichtig."]
    result = buffer_tokens_until_sentence(chunks)
    assert len(result) == 2
    assert result[0] == "z.B. das ist klar."
    assert result[1] == "Wirklich wichtig."


def test_empty_and_no_boundary_inputs():
    """Test edge cases: empty input and text without sentence boundaries."""
    assert buffer_tokens_until_sentence([]) == []
    assert buffer_tokens_until_sentence(["Hello world"]) == ["Hello world"]
    assert buffer_tokens_until_sentence(["Hallo Welt."]) == ["Hallo Welt."]


def test_agent_class_selection():
    """Test agent class selection based on streaming configuration."""
    class _StubStreamingAgent:
        pass

    class _StubNonStreamingAgent:
        pass

    def select_agent_class(enabled: bool):
        return _StubStreamingAgent if enabled else _StubNonStreamingAgent

    assert select_agent_class(True) is _StubStreamingAgent
    assert select_agent_class(False) is _StubNonStreamingAgent

    os.environ["VOICEBOT_STREAMING_ENABLED"] = "true"
    enabled = os.getenv("VOICEBOT_STREAMING_ENABLED", "true").lower() == "true"
    assert select_agent_class(enabled) is _StubStreamingAgent

    os.environ["VOICEBOT_STREAMING_ENABLED"] = "false"
    enabled = os.getenv("VOICEBOT_STREAMING_ENABLED", "true").lower() == "true"
    assert select_agent_class(enabled) is _StubNonStreamingAgent

    os.environ.pop("VOICEBOT_STREAMING_ENABLED", None)


def test_nexo_agent_accepts_instructions_kwarg():
    """Test that NexoAgent accepts 'instructions' keyword argument."""
    class _StubFixedNexoAgent:
        def __init__(self, instructions: str = ""):
            self.instructions = instructions

    try:
        agent = _StubFixedNexoAgent(instructions="test prompt")
        assert agent.instructions == "test prompt"
    except TypeError:
        pytest.fail("NexoAgent must accept 'instructions' keyword argument")
