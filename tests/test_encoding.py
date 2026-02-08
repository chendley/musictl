"""Tests for core.encoding module."""

import pytest

from musictl.core.encoding import (
    detect_non_utf8_tags,
    try_decode,
    guess_encoding,
    ENCODINGS,
)


def test_detect_non_utf8_tags_clean_file(sample_mp3):
    """Test that clean UTF-8 files are not flagged."""
    suspect = detect_non_utf8_tags(sample_mp3)
    assert suspect == {}


def test_detect_non_utf8_tags_bad_encoding(sample_mp3_bad_encoding):
    """Test detection of mis-encoded tags."""
    suspect = detect_non_utf8_tags(sample_mp3_bad_encoding)

    # Should detect the mis-encoded TIT2 tag
    assert len(suspect) > 0
    assert "TIT2" in suspect
    assert isinstance(suspect["TIT2"], bytes)


def test_try_decode_valid():
    """Test successful decoding."""
    cyrillic_bytes = "Тест".encode("cp1251")
    result = try_decode(cyrillic_bytes, "cp1251")

    assert result == "Тест"


def test_try_decode_invalid_encoding():
    """Test decoding with wrong encoding returns None."""
    text_bytes = "Hello".encode("utf-8")
    result = try_decode(text_bytes, "invalid_encoding_name")

    assert result is None


def test_try_decode_invalid_bytes():
    """Test decoding invalid bytes returns None."""
    invalid_bytes = b"\xFF\xFE\xFD"
    result = try_decode(invalid_bytes, "utf-8")

    assert result is None


def test_guess_encoding_cyrillic():
    """Test guessing Cyrillic encoding."""
    cyrillic_bytes = "Привет".encode("cp1251")
    guesses = guess_encoding(cyrillic_bytes)

    # Should return multiple guesses
    assert len(guesses) > 0

    # Each guess should be a tuple (encoding, description, decoded_text)
    for enc, desc, decoded in guesses:
        assert enc in ENCODINGS
        assert isinstance(desc, str)
        assert isinstance(decoded, str)

    # cp1251 should be one of the valid decodings
    encodings = [enc for enc, _, _ in guesses]
    assert "cp1251" in encodings


def test_guess_encoding_japanese():
    """Test guessing Japanese encoding."""
    japanese_bytes = "こんにちは".encode("shift_jis")
    guesses = guess_encoding(japanese_bytes)

    encodings = [enc for enc, _, _ in guesses]
    assert "shift_jis" in encodings


def test_encodings_dictionary():
    """Test that ENCODINGS dictionary is properly structured."""
    assert len(ENCODINGS) > 0

    # Should contain common encodings
    assert "cp1251" in ENCODINGS
    assert "utf-8" not in ENCODINGS  # UTF-8 is the target, not source

    # All values should be descriptions
    for key, value in ENCODINGS.items():
        assert isinstance(key, str)
        assert isinstance(value, str)


def test_guess_encoding_empty_bytes():
    """Test guessing encoding with empty bytes."""
    guesses = guess_encoding(b"")

    # Should handle gracefully - either return empty list or valid decodings
    assert isinstance(guesses, list)


def test_detect_non_utf8_tags_flac(sample_flac):
    """Test that FLAC files return empty dict (only works on ID3)."""
    suspect = detect_non_utf8_tags(sample_flac)

    # FLAC doesn't use ID3, so should return empty
    assert suspect == {}
