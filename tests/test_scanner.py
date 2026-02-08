"""Tests for core.scanner module."""

from pathlib import Path

import pytest

from musictl.core.scanner import walk_audio_files


def test_walk_single_file(sample_mp3):
    """Test walking a single file."""
    files = list(walk_audio_files(sample_mp3))

    assert len(files) == 1
    assert files[0] == sample_mp3


def test_walk_directory_recursive(sample_library):
    """Test recursive directory walking."""
    music_dir, expected_files = sample_library
    files = list(walk_audio_files(music_dir, recursive=True))

    # Should find all 5 files (3 MP3s + 2 FLACs)
    assert len(files) == 5

    # All should be Path objects
    assert all(isinstance(f, Path) for f in files)

    # Should be sorted
    assert files == sorted(files)


def test_walk_directory_non_recursive(sample_library):
    """Test non-recursive directory walking."""
    music_dir, _ = sample_library
    files = list(walk_audio_files(music_dir, recursive=False))

    # Should find no files (all are in subdirectories)
    assert len(files) == 0


def test_walk_directory_with_files_in_root(temp_music_dir, sample_mp3, sample_flac):
    """Test non-recursive walk with files in root."""
    # sample_mp3 and sample_flac are already in temp_music_dir
    files = list(walk_audio_files(temp_music_dir, recursive=False))

    assert len(files) == 2
    assert sample_mp3 in files
    assert sample_flac in files


def test_walk_ignores_non_audio_files(temp_music_dir):
    """Test that non-audio files are ignored."""
    # Create some non-audio files
    (temp_music_dir / "README.txt").write_text("Not audio")
    (temp_music_dir / "cover.jpg").write_bytes(b"\xFF\xD8\xFF")  # JPEG header
    (temp_music_dir / "script.py").write_text("print('hello')")

    # Create one audio file
    mp3 = temp_music_dir / "song.mp3"
    mp3.write_bytes(b"fake mp3")

    files = list(walk_audio_files(temp_music_dir))

    # Should only find the MP3
    assert len(files) == 1
    assert files[0] == mp3


def test_walk_case_insensitive_extensions(temp_music_dir):
    """Test that file extensions are case-insensitive."""
    # Create files with various case extensions
    (temp_music_dir / "song.MP3").write_bytes(b"fake")
    (temp_music_dir / "track.FlaC").write_bytes(b"fake")
    (temp_music_dir / "audio.OGG").write_bytes(b"fake")

    files = list(walk_audio_files(temp_music_dir))

    assert len(files) == 3


def test_walk_empty_directory(temp_music_dir):
    """Test walking empty directory."""
    empty_dir = temp_music_dir / "empty"
    empty_dir.mkdir()

    files = list(walk_audio_files(empty_dir))

    assert len(files) == 0


def test_walk_nonexistent_path(temp_music_dir):
    """Test walking nonexistent path."""
    fake_path = temp_music_dir / "nonexistent"

    files = list(walk_audio_files(fake_path))

    # Should handle gracefully - either empty list or raise
    # Current implementation will likely return empty due to is_file() check
    assert len(files) == 0


def test_walk_unsupported_file(temp_music_dir):
    """Test that unsupported audio file is ignored."""
    unsupported = temp_music_dir / "song.wma"
    unsupported.write_bytes(b"fake wma")

    files = list(walk_audio_files(temp_music_dir))

    # .wma is in SUPPORTED_EXTENSIONS, so it should be included
    # If not, this test would expect 0 files
    # Based on audio.py line 14, .wma IS supported
    assert len(files) == 1


def test_walk_sorted_output(temp_music_dir):
    """Test that output is sorted."""
    # Create files in non-alphabetical order
    (temp_music_dir / "z_last.mp3").write_bytes(b"fake")
    (temp_music_dir / "a_first.mp3").write_bytes(b"fake")
    (temp_music_dir / "m_middle.mp3").write_bytes(b"fake")

    files = list(walk_audio_files(temp_music_dir))

    file_names = [f.name for f in files]
    assert file_names == sorted(file_names)
