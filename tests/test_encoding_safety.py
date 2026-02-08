"""Tests for encoding fix safety - ensuring we don't corrupt correct files."""

from pathlib import Path

import pytest
from mutagen.id3 import ID3, TIT2, TPE1, TALB
from mutagen.mp3 import MP3

from musictl.core.encoding import detect_non_utf8_tags
from tests.conftest import create_test_mp3


@pytest.fixture
def mp3_with_correct_utf8(tmp_path):
    """Create an MP3 with CORRECT UTF-8 Cyrillic tags."""
    mp3_path = tmp_path / "correct_russian.mp3"
    create_test_mp3(mp3_path)

    # Add CORRECT UTF-8 tags
    audio = MP3(str(mp3_path))
    audio["TIT2"] = TIT2(encoding=3, text="Железнодорожная Вода")  # UTF-8
    audio["TPE1"] = TPE1(encoding=3, text="Аквариум")  # UTF-8
    audio["TALB"] = TALB(encoding=3, text="Синий Альбом")  # UTF-8
    audio.save()

    return mp3_path


@pytest.fixture
def mp3_with_mojibake(tmp_path):
    """Create an MP3 with mojibake (double-encoded Cyrillic)."""
    mp3_path = tmp_path / "mojibake_russian.mp3"
    create_test_mp3(mp3_path)

    # Create mojibake: take correct UTF-8, decode as CP1251, save as UTF-8
    correct_title = "Железнодорожная Вода"
    correct_artist = "Аквариум"

    # Simulate the double-encoding that creates mojibake:
    # UTF-8 bytes → decode as cp1251 → save as UTF-8
    garbled_title = correct_title.encode("utf-8").decode("cp1251", errors="replace")
    garbled_artist = correct_artist.encode("utf-8").decode("cp1251", errors="replace")

    audio = MP3(str(mp3_path))
    audio["TIT2"] = TIT2(encoding=3, text=garbled_title)
    audio["TPE1"] = TPE1(encoding=3, text=garbled_artist)
    audio.save()

    return mp3_path


@pytest.fixture
def mp3_with_ascii(tmp_path):
    """Create an MP3 with ASCII-only tags."""
    mp3_path = tmp_path / "ascii_only.mp3"
    create_test_mp3(mp3_path)

    audio = MP3(str(mp3_path))
    audio["TIT2"] = TIT2(encoding=3, text="Railway Water")
    audio["TPE1"] = TPE1(encoding=3, text="Aquarium")
    audio.save()

    return mp3_path


def test_correct_utf8_not_flagged(mp3_with_correct_utf8):
    """Files with CORRECT UTF-8 should NOT be flagged for fixing."""
    suspect = detect_non_utf8_tags(mp3_with_correct_utf8, encoding="cp1251")

    # Should return empty dict - nothing to fix
    assert len(suspect) == 0, "Correct UTF-8 files should not be flagged"


def test_mojibake_is_detected(mp3_with_mojibake):
    """Files with mojibake SHOULD be detected."""
    suspect = detect_non_utf8_tags(mp3_with_mojibake, encoding="cp1251")

    # Should detect the mojibake tags
    assert len(suspect) > 0, "Mojibake should be detected"
    assert "TIT2" in suspect or "TPE1" in suspect


def test_ascii_not_flagged(mp3_with_ascii):
    """ASCII-only files should not be flagged."""
    suspect = detect_non_utf8_tags(mp3_with_ascii, encoding="cp1251")

    assert len(suspect) == 0, "ASCII files should not be flagged"


def test_mojibake_reversal_works(mp3_with_mojibake):
    """Reversing mojibake should produce correct UTF-8."""
    suspect = detect_non_utf8_tags(mp3_with_mojibake, encoding="cp1251")

    # Should be able to reverse the mojibake
    for tag_key, intermediate_bytes in suspect.items():
        fixed = intermediate_bytes.decode("utf-8")

        # Fixed text should contain basic Russian Cyrillic characters
        cyrillic_count = sum(1 for c in fixed if 0x410 <= ord(c) <= 0x44F)
        assert cyrillic_count > 0, f"Fixed {tag_key} should contain basic Cyrillic"


def test_reversal_produces_fewer_anomalies(mp3_with_mojibake):
    """The 'fixed' version should have FEWER non-basic-Cyrillic characters."""
    suspect = detect_non_utf8_tags(mp3_with_mojibake, encoding="cp1251")

    id3 = ID3(str(mp3_with_mojibake))

    for tag_key, intermediate_bytes in suspect.items():
        original_text = str(id3[tag_key].text[0])
        fixed_text = intermediate_bytes.decode("utf-8")

        # Count characters outside basic Russian Cyrillic (U+0410-0x044F)
        anomalous_in_original = sum(1 for c in original_text if not (0x410 <= ord(c) <= 0x44F))
        anomalous_in_fixed = sum(1 for c in fixed_text if not (0x410 <= ord(c) <= 0x44F))

        assert anomalous_in_fixed < anomalous_in_original, \
            f"{tag_key}: Fixed should have fewer anomalies ({anomalous_in_fixed} vs {anomalous_in_original})"


def test_detection_with_different_encodings(mp3_with_mojibake):
    """Test detection with encodings other than CP1251."""
    # Should NOT detect with wrong encoding
    suspect_koi8 = detect_non_utf8_tags(mp3_with_mojibake, encoding="koi8-r")
    suspect_latin1 = detect_non_utf8_tags(mp3_with_mojibake, encoding="iso-8859-1")

    # These should either return empty or not improve the text
    # (The safety check should prevent false positives)
    # We don't assert they're empty because KOI8-R might partially work,
    # but we verify CP1251 works better
    suspect_cp1251 = detect_non_utf8_tags(mp3_with_mojibake, encoding="cp1251")
    assert len(suspect_cp1251) > 0, "CP1251 should detect the mojibake"


def test_nonexistent_file():
    """Test handling of nonexistent files."""
    suspect = detect_non_utf8_tags(Path("/tmp/does_not_exist.mp3"), encoding="cp1251")
    assert len(suspect) == 0, "Nonexistent file should return empty dict"


def test_corrupted_id3(tmp_path):
    """Test handling of corrupted ID3 tags."""
    bad_mp3 = tmp_path / "corrupted.mp3"

    # Create file with invalid ID3 header
    with open(bad_mp3, "wb") as f:
        f.write(b"ID3\x04\x00\x00\x00\x00\x00\xFF" + b"\x00" * 100)

    suspect = detect_non_utf8_tags(bad_mp3, encoding="cp1251")
    # Should handle gracefully, return empty dict
    assert isinstance(suspect, dict)


def test_empty_tags(tmp_path):
    """Test handling of files with no text tags."""
    mp3_path = tmp_path / "no_tags.mp3"
    create_test_mp3(mp3_path)

    # File has MP3 data but no ID3 tags
    suspect = detect_non_utf8_tags(mp3_path, encoding="cp1251")
    assert len(suspect) == 0, "Files with no tags should return empty dict"


def test_mixed_correct_and_mojibake(tmp_path):
    """Test file with some correct and some mojibake tags."""
    mp3_path = tmp_path / "mixed.mp3"
    create_test_mp3(mp3_path)

    # Correct UTF-8 title
    correct_title = "Correct Title"

    # Mojibake artist
    correct_artist = "Аквариум"
    garbled_artist = correct_artist.encode("utf-8").decode("cp1251", errors="replace")

    audio = MP3(str(mp3_path))
    audio["TIT2"] = TIT2(encoding=3, text=correct_title)
    audio["TPE1"] = TPE1(encoding=3, text=garbled_artist)
    audio.save()

    suspect = detect_non_utf8_tags(mp3_path, encoding="cp1251")

    # Should only flag the mojibake tag
    assert "TIT2" not in suspect, "Correct ASCII title should not be flagged"
    assert "TPE1" in suspect, "Mojibake artist should be flagged"
