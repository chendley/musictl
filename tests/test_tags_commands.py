"""Integration tests for tag commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner
from mutagen.mp3 import MP3
from mutagen.id3 import TIT2, TPE1

from musictl.cli import app

runner = CliRunner()


class TestTagsShow:
    """Tests for 'musictl tags show' command."""

    def test_show_single_mp3(self, sample_mp3):
        """Test showing tags for a single MP3 file."""
        result = runner.invoke(app, ["tags", "show", str(sample_mp3)])

        assert result.exit_code == 0
        assert "Test Song" in result.stdout
        assert "Test Artist" in result.stdout
        assert "MP3" in result.stdout

    def test_show_single_flac(self, sample_flac):
        """Test showing tags for a single FLAC file."""
        result = runner.invoke(app, ["tags", "show", str(sample_flac)])

        assert result.exit_code == 0
        assert "Test Song" in result.stdout or "test song" in result.stdout.lower()
        assert "FLAC" in result.stdout

    def test_show_directory_recursive(self, sample_library):
        """Test showing tags for all files in a directory."""
        music_dir, files = sample_library
        result = runner.invoke(app, ["tags", "show", str(music_dir), "--recursive"])

        assert result.exit_code == 0
        # Should show all 5 files
        assert "Rock Song" in result.stdout
        assert "Jazz Track" in result.stdout

    def test_show_directory_non_recursive(self, temp_music_dir, sample_mp3):
        """Test non-recursive show."""
        result = runner.invoke(app, ["tags", "show", str(temp_music_dir), "--no-recursive"])

        assert result.exit_code == 0
        # Should find the sample_mp3 in the root
        assert "Test Song" in result.stdout

    def test_show_nonexistent_path(self):
        """Test showing tags for nonexistent path."""
        result = runner.invoke(app, ["tags", "show", "/nonexistent/path"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_show_empty_directory(self, temp_music_dir):
        """Test showing tags in directory with no audio files."""
        empty_dir = temp_music_dir / "empty"
        empty_dir.mkdir()

        result = runner.invoke(app, ["tags", "show", str(empty_dir)])

        assert result.exit_code == 0
        assert "No audio files found" in result.stdout


class TestTagsFixEncoding:
    """Tests for 'musictl tags fix-encoding' command."""

    def test_fix_encoding_dry_run(self, sample_mp3_bad_encoding):
        """Test fix-encoding in dry-run mode."""
        result = runner.invoke(app, [
            "tags", "fix-encoding",
            str(sample_mp3_bad_encoding),
            "--from", "cp1251"
        ])

        assert result.exit_code == 0
        assert "Dry run" in result.stdout
        assert "would be fixed" in result.stdout

        # File should not be modified
        audio = MP3(str(sample_mp3_bad_encoding))
        # Tag should still be mis-encoded
        assert "TIT2" in audio

    def test_fix_encoding_apply(self, sample_mp3_bad_encoding):
        """Test fix-encoding with --apply flag."""
        result = runner.invoke(app, [
            "tags", "fix-encoding",
            str(sample_mp3_bad_encoding),
            "--from", "cp1251",
            "--apply"
        ])

        assert result.exit_code == 0
        assert "Fixed" in result.stdout

        # Verify the file was actually modified
        audio = MP3(str(sample_mp3_bad_encoding))
        title = str(audio["TIT2"])
        # Should now contain proper Cyrillic
        assert "Тест" in title

    def test_fix_encoding_invalid_encoding(self, sample_mp3):
        """Test fix-encoding with invalid encoding."""
        result = runner.invoke(app, [
            "tags", "fix-encoding",
            str(sample_mp3),
            "--from", "invalid_encoding"
        ])

        assert result.exit_code == 1
        assert "Unknown encoding" in result.stdout

    def test_fix_encoding_no_mp3_files(self, sample_flac):
        """Test fix-encoding on non-MP3 file."""
        result = runner.invoke(app, [
            "tags", "fix-encoding",
            str(sample_flac.parent),
            "--from", "cp1251"
        ])

        assert result.exit_code == 0
        assert "No MP3 files found" in result.stdout

    def test_fix_encoding_clean_file(self, sample_mp3):
        """Test fix-encoding on file with clean UTF-8 tags."""
        result = runner.invoke(app, [
            "tags", "fix-encoding",
            str(sample_mp3),
            "--from", "cp1251"
        ])

        assert result.exit_code == 0
        assert "skipped" in result.stdout.lower() or "already OK" in result.stdout


class TestTagsStripV1:
    """Tests for 'musictl tags strip-v1' command."""

    def test_strip_v1_dry_run(self, sample_mp3_with_v1):
        """Test strip-v1 in dry-run mode."""
        result = runner.invoke(app, [
            "tags", "strip-v1",
            str(sample_mp3_with_v1)
        ])

        assert result.exit_code == 0
        assert "Dry run" in result.stdout
        assert "files would be processed" in result.stdout

        # Verify file still has ID3v1
        with open(sample_mp3_with_v1, "rb") as f:
            f.seek(-128, 2)
            assert f.read(3) == b"TAG"

    def test_strip_v1_apply(self, sample_mp3_with_v1):
        """Test strip-v1 with --apply flag."""
        result = runner.invoke(app, [
            "tags", "strip-v1",
            str(sample_mp3_with_v1),
            "--apply"
        ])

        assert result.exit_code == 0
        assert "Stripped ID3v1" in result.stdout

        # Verify ID3v1 tag is gone
        with open(sample_mp3_with_v1, "rb") as f:
            f.seek(-128, 2)
            assert f.read(3) != b"TAG"

    def test_strip_v1_no_id3v1(self, sample_mp3):
        """Test strip-v1 on file without ID3v1."""
        result = runner.invoke(app, [
            "tags", "strip-v1",
            str(sample_mp3)
        ])

        assert result.exit_code == 0
        # Should indicate no files had ID3v1
        assert "0 files" in result.stdout or "Dry run: 0" in result.stdout

    def test_strip_v1_directory(self, temp_music_dir, sample_mp3_with_v1):
        """Test strip-v1 on directory."""
        result = runner.invoke(app, [
            "tags", "strip-v1",
            str(temp_music_dir),
            "--recursive"
        ])

        assert result.exit_code == 0
        # Should find at least one file with ID3v1


class TestTagsNormalize:
    """Tests for 'musictl tags normalize' command."""

    def test_normalize_dry_run(self, sample_messy_tags):
        """Test normalize in dry-run mode."""
        result = runner.invoke(app, [
            "tags", "normalize",
            str(sample_messy_tags)
        ])

        assert result.exit_code == 0
        assert "Dry run" in result.stdout
        assert "would be normalized" in result.stdout

        # Verify file not modified
        audio = MP3(str(sample_messy_tags))
        title = str(audio["TIT2"])
        # Should still have extra spaces
        assert "  " in title

    def test_normalize_apply(self, sample_messy_tags):
        """Test normalize with --apply flag."""
        result = runner.invoke(app, [
            "tags", "normalize",
            str(sample_messy_tags),
            "--apply"
        ])

        assert result.exit_code == 0
        assert "Normalized" in result.stdout

        # Verify tags are cleaned up
        audio = MP3(str(sample_messy_tags))
        title = str(audio["TIT2"])
        artist = str(audio["TPE1"])

        # Should have whitespace stripped and collapsed
        assert title == "Song With Spaces"
        assert artist == "Artist"

        # Empty tag should be removed
        assert "TALB" not in audio

    def test_normalize_various_artists(self, sample_various_artists):
        """Test normalization of Various Artists variants."""
        result = runner.invoke(app, [
            "tags", "normalize",
            str(sample_various_artists[0].parent),
            "--apply"
        ])

        assert result.exit_code == 0

        # Check that all variants are normalized to "Various Artists"
        for mp3_path in sample_various_artists:
            audio = MP3(str(mp3_path))
            artist = str(audio["TPE1"])
            assert artist == "Various Artists"

    def test_normalize_clean_file(self, sample_mp3):
        """Test normalize on file with clean tags."""
        result = runner.invoke(app, [
            "tags", "normalize",
            str(sample_mp3)
        ])

        assert result.exit_code == 0
        # Should indicate no files needed normalization
        assert "0 files" in result.stdout or "Dry run: 0" in result.stdout

    def test_normalize_directory(self, sample_library):
        """Test normalize on directory with multiple files."""
        music_dir, files = sample_library
        result = runner.invoke(app, [
            "tags", "normalize",
            str(music_dir),
            "--recursive"
        ])

        assert result.exit_code == 0
        # Should complete without errors


class TestTagsCommandsEdgeCases:
    """Edge case tests for tag commands."""

    def test_tags_no_subcommand(self):
        """Test running 'musictl tags' without subcommand."""
        result = runner.invoke(app, ["tags"])

        # Typer exits with code 2 when subcommand is missing
        assert result.exit_code == 2
        # Should show error message
        output = result.stdout + result.stderr
        assert "Missing command" in output

    def test_tags_help(self):
        """Test 'musictl tags --help'."""
        result = runner.invoke(app, ["tags", "--help"])

        assert result.exit_code == 0
        assert "Audio tag operations" in result.stdout
