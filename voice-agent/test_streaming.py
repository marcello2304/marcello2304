import re
import pytest

SENTENCE_PATTERN = r'(?<=[.!?])\s+(?=[A-Z])'
MAX_SENTENCE_LENGTH = 250

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
                sentence = sentence[:MAX_SENTENCE_LENGTH-3] + "..."

            if sentence:
                results.append(sentence)

    # Yield remaining text
    if buffer.strip():
        final_text = buffer.strip()
        if len(final_text) > MAX_SENTENCE_LENGTH:
            final_text = final_text[:MAX_SENTENCE_LENGTH-3] + "..."
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
