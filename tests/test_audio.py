"""Tests for core.audio module."""

from pathlib import Path

import pytest
from mutagen.id3 import TIT2

from musictl.core.audio import read_audio, AudioInfo, SUPPORTED_EXTENSIONS


def test_read_mp3_basic(sample_mp3):
    """Test reading basic MP3 file metadata."""
    info = read_audio(sample_mp3)

    assert info.error is None
    assert info.format == "MP3"
    assert info.path == sample_mp3
    assert info.has_id3v2
    assert not info.has_id3v1
    assert "TIT2" in info.tags
    assert "Test Song" in info.tags["TIT2"]


def test_read_mp3_with_id3v1(sample_mp3_with_v1):
    """Test detection of ID3v1 tags."""
    info = read_audio(sample_mp3_with_v1)

    assert info.error is None
    assert info.has_id3v1
    assert info.has_id3v2


def test_read_flac_basic(sample_flac):
    """Test reading basic FLAC file metadata."""
    info = read_audio(sample_flac)

    assert info.error is None
    assert info.format == "FLAC"
    assert "TITLE" in info.tags or "title" in info.tags


def test_read_nonexistent_file(temp_music_dir):
    """Test reading nonexistent file returns error."""
    fake_path = temp_music_dir / "nonexistent.mp3"
    info = read_audio(fake_path)

    assert info.error is not None


def test_read_invalid_audio_file(temp_music_dir):
    """Test reading invalid audio file."""
    bad_file = temp_music_dir / "not_audio.mp3"
    bad_file.write_text("This is not an audio file")

    info = read_audio(bad_file)

    assert info.error is not None


def test_audio_info_properties(sample_mp3):
    """Test AudioInfo computed properties."""
    info = read_audio(sample_mp3)

    # Duration string formatting
    assert isinstance(info.duration_str, str)
    assert ":" in info.duration_str

    # Sample rate string formatting
    assert isinstance(info.sample_rate_str, str)

    # is_hires property
    assert not info.is_hires  # Standard MP3 is not hi-res


def test_supported_extensions():
    """Test that SUPPORTED_EXTENSIONS contains expected formats."""
    assert ".mp3" in SUPPORTED_EXTENSIONS
    assert ".flac" in SUPPORTED_EXTENSIONS
    assert ".ogg" in SUPPORTED_EXTENSIONS
    assert ".m4a" in SUPPORTED_EXTENSIONS


def test_read_mp3_bad_encoding(sample_mp3_bad_encoding):
    """Test reading MP3 with mis-encoded tags doesn't crash."""
    info = read_audio(sample_mp3_bad_encoding)

    # Should still read successfully, even if tags are garbled
    assert info.error is None
    assert info.format == "MP3"
    assert "TIT2" in info.tags


def test_audio_info_dataclass_defaults():
    """Test AudioInfo default values."""
    info = AudioInfo(path=Path("/fake/path.mp3"))

    assert info.format == ""
    assert info.sample_rate == 0
    assert info.bit_depth == 0
    assert info.channels == 0
    assert info.duration == 0.0
    assert info.bitrate == 0
    assert info.tags == {}
    assert not info.has_id3v1
    assert not info.has_id3v2
    assert info.error is None
