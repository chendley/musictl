"""Integration tests for scan commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from musictl.cli import app

runner = CliRunner()


class TestScanEncoding:
    """Tests for 'musictl scan encoding' command."""

    def test_scan_encoding_clean_files(self, sample_mp3):
        """Test scanning files with clean UTF-8 encoding."""
        result = runner.invoke(app, ["scan", "encoding", str(sample_mp3.parent)])

        assert result.exit_code == 0
        assert "0 files with suspect encoding" in result.stdout or "Found 0 files" in result.stdout

    def test_scan_encoding_bad_encoding(self, sample_mp3_bad_encoding):
        """Test scanning files with mis-encoded tags."""
        result = runner.invoke(app, ["scan", "encoding", str(sample_mp3_bad_encoding.parent)])

        assert result.exit_code == 0
        assert "Suspect encoding" in result.stdout
        # Should show the file name and find at least one file with suspect encoding
        assert "bad_encoding.mp3" in result.stdout
        assert "Found 1 files with suspect encoding" in result.stdout or "1 files" in result.stdout

    def test_scan_encoding_no_mp3_files(self, sample_flac):
        """Test scanning directory with no MP3 files."""
        result = runner.invoke(app, ["scan", "encoding", str(sample_flac.parent)])

        assert result.exit_code == 0
        assert "No MP3 files found" in result.stdout

    def test_scan_encoding_recursive(self, sample_library):
        """Test recursive scanning."""
        music_dir, files = sample_library
        result = runner.invoke(app, ["scan", "encoding", str(music_dir), "--recursive"])

        assert result.exit_code == 0
        # Should scan all MP3 files in subdirectories

    def test_scan_encoding_non_recursive(self, temp_music_dir, sample_mp3):
        """Test non-recursive scanning."""
        # Create a subdirectory with an MP3
        subdir = temp_music_dir / "subdir"
        subdir.mkdir()

        result = runner.invoke(app, ["scan", "encoding", str(temp_music_dir), "--no-recursive"])

        assert result.exit_code == 0
        # Should only scan the root directory

    def test_scan_encoding_nonexistent_path(self):
        """Test scanning nonexistent path."""
        result = runner.invoke(app, ["scan", "encoding", "/nonexistent/path"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


class TestScanHires:
    """Tests for 'musictl scan hires' command."""

    def test_scan_hires_standard_files(self, sample_mp3, sample_flac):
        """Test scanning standard sample rate files."""
        result = runner.invoke(app, ["scan", "hires", str(sample_mp3.parent)])

        assert result.exit_code == 0
        # Standard 44.1kHz files should not be hi-res
        assert "No files above" in result.stdout or "Found 0 hi-res" in result.stdout

    def test_scan_hires_with_hires_file(self, sample_flac_hires):
        """Test scanning with actual hi-res file."""
        result = runner.invoke(app, ["scan", "hires", str(sample_flac_hires.parent)])

        assert result.exit_code == 0
        # Should find the hi-res file
        assert "hires" in result.stdout.lower() or "96" in result.stdout

    def test_scan_hires_custom_threshold(self, sample_mp3):
        """Test scanning with custom threshold."""
        # Use a threshold lower than standard 44.1kHz
        result = runner.invoke(app, ["scan", "hires", str(sample_mp3.parent), "--threshold", "40000"])

        assert result.exit_code == 0
        # 44.1kHz file should now be considered hi-res
        assert "sample.mp3" in result.stdout or "44" in result.stdout

    def test_scan_hires_recursive(self, sample_library):
        """Test recursive hi-res scanning."""
        music_dir, files = sample_library
        result = runner.invoke(app, ["scan", "hires", str(music_dir), "--recursive"])

        assert result.exit_code == 0
        # Should scan all audio files recursively

    def test_scan_hires_non_recursive(self, temp_music_dir, sample_flac):
        """Test non-recursive hi-res scanning."""
        result = runner.invoke(app, ["scan", "hires", str(temp_music_dir), "--no-recursive"])

        assert result.exit_code == 0

    def test_scan_hires_empty_directory(self, temp_music_dir):
        """Test scanning empty directory."""
        empty_dir = temp_music_dir / "empty"
        empty_dir.mkdir()

        result = runner.invoke(app, ["scan", "hires", str(empty_dir)])

        assert result.exit_code == 0
        assert "No audio files found" in result.stdout

    def test_scan_hires_table_output(self, sample_flac_hires):
        """Test that hi-res scan outputs a formatted table."""
        result = runner.invoke(app, ["scan", "hires", str(sample_flac_hires.parent)])

        assert result.exit_code == 0
        # Should show table headers
        assert "Format" in result.stdout or "Sample Rate" in result.stdout


class TestScanCommandsEdgeCases:
    """Edge case tests for scan commands."""

    def test_scan_no_subcommand(self):
        """Test running 'musictl scan' without subcommand."""
        result = runner.invoke(app, ["scan"])

        # Typer exits with code 2 when subcommand is missing
        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "Missing command" in output

    def test_scan_help(self):
        """Test 'musictl scan --help'."""
        result = runner.invoke(app, ["scan", "--help"])

        assert result.exit_code == 0
        assert "Library scanning" in result.stdout or "scanning" in result.stdout.lower()

    def test_scan_encoding_help(self):
        """Test 'musictl scan encoding --help'."""
        result = runner.invoke(app, ["scan", "encoding", "--help"])

        assert result.exit_code == 0
        assert "non-UTF-8" in result.stdout or "encoding" in result.stdout.lower()

    def test_scan_hires_help(self):
        """Test 'musictl scan hires --help'."""
        result = runner.invoke(app, ["scan", "hires", "--help"])

        assert result.exit_code == 0
        assert "hi-res" in result.stdout.lower() or "sample rate" in result.stdout.lower()
