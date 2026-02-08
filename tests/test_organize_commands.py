"""Integration tests for scan library and organize commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from musictl.cli import app

runner = CliRunner()


class TestScanLibrary:
    """Tests for 'musictl scan library' command."""

    def test_scan_library_basic(self, sample_library):
        """Test basic library scan."""
        music_dir, files = sample_library
        result = runner.invoke(app, ["scan", "library", str(music_dir)])

        assert result.exit_code == 0
        assert "Library Statistics" in result.stdout
        assert "Format Distribution" in result.stdout
        assert "Sample Rate Distribution" in result.stdout
        assert "Summary:" in result.stdout
        # Should show both MP3 and FLAC
        assert "MP3" in result.stdout
        assert "FLAC" in result.stdout

    def test_scan_library_single_file(self, sample_mp3):
        """Test scanning a single file."""
        result = runner.invoke(app, ["scan", "library", str(sample_mp3)])

        assert result.exit_code == 0
        assert "Library Statistics" in result.stdout
        assert "Total files: 1" in result.stdout

    def test_scan_library_empty_directory(self, temp_music_dir):
        """Test scanning empty directory."""
        empty_dir = temp_music_dir / "empty"
        empty_dir.mkdir()

        result = runner.invoke(app, ["scan", "library", str(empty_dir)])

        assert result.exit_code == 0
        assert "No audio files found" in result.stdout

    def test_scan_library_nonexistent_path(self):
        """Test scanning nonexistent path."""
        result = runner.invoke(app, ["scan", "library", "/nonexistent/path"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_scan_library_recursive(self, sample_library):
        """Test recursive scanning."""
        music_dir, files = sample_library
        result = runner.invoke(app, ["scan", "library", str(music_dir), "--recursive"])

        assert result.exit_code == 0
        # Should find all 5 files in subdirectories
        assert "Total files: 5" in result.stdout

    def test_scan_library_non_recursive(self, temp_music_dir, sample_mp3):
        """Test non-recursive scanning."""
        # sample_mp3 is in the root
        result = runner.invoke(app, ["scan", "library", str(temp_music_dir), "--no-recursive"])

        assert result.exit_code == 0
        # Should only find the one file in root
        assert "Total files: 1" in result.stdout

    def test_scan_library_shows_duration(self, sample_library):
        """Test that scan shows total duration."""
        music_dir, files = sample_library
        result = runner.invoke(app, ["scan", "library", str(music_dir)])

        assert result.exit_code == 0
        assert "Total duration:" in result.stdout

    def test_scan_library_shows_size(self, sample_library):
        """Test that scan shows total file size."""
        music_dir, files = sample_library
        result = runner.invoke(app, ["scan", "library", str(music_dir)])

        assert result.exit_code == 0
        assert "Total size:" in result.stdout


class TestOrganizeByFormat:
    """Tests for 'musictl organize by-format' command."""

    def test_organize_by_format_dry_run(self, sample_library, tmp_path):
        """Test organize by-format in dry-run mode."""
        music_dir, files = sample_library
        dest = tmp_path / "organized"

        result = runner.invoke(app, [
            "organize", "by-format",
            str(music_dir),
            "--dest", str(dest)
        ])

        assert result.exit_code == 0
        assert "Dry run" in result.stdout
        assert "Organization Plan" in result.stdout
        assert "MP3" in result.stdout
        assert "FLAC" in result.stdout
        # Destination should not be created in dry-run
        assert not dest.exists()

    def test_organize_by_format_apply(self, sample_library, tmp_path):
        """Test organize by-format with --apply."""
        music_dir, files = sample_library
        dest = tmp_path / "organized"

        result = runner.invoke(app, [
            "organize", "by-format",
            str(music_dir),
            "--dest", str(dest),
            "--apply"
        ])

        assert result.exit_code == 0
        assert "Successfully moved" in result.stdout

        # Verify destination structure
        assert dest.exists()
        assert (dest / "MP3").exists()
        assert (dest / "FLAC").exists()

        # Verify files were moved
        mp3_files = list((dest / "MP3").glob("*.mp3"))
        flac_files = list((dest / "FLAC").glob("*.flac"))
        assert len(mp3_files) == 3
        assert len(flac_files) == 2

    def test_organize_by_format_missing_dest(self, sample_mp3):
        """Test organize without --dest flag."""
        result = runner.invoke(app, [
            "organize", "by-format",
            str(sample_mp3.parent)
        ])

        # Should fail - dest is required
        assert result.exit_code != 0

    def test_organize_by_format_nonexistent_source(self, tmp_path):
        """Test organize with nonexistent source."""
        result = runner.invoke(app, [
            "organize", "by-format",
            "/nonexistent/path",
            "--dest", str(tmp_path / "out")
        ])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_organize_by_format_empty_directory(self, temp_music_dir, tmp_path):
        """Test organize on empty directory."""
        empty_dir = temp_music_dir / "empty"
        empty_dir.mkdir()

        result = runner.invoke(app, [
            "organize", "by-format",
            str(empty_dir),
            "--dest", str(tmp_path / "out")
        ])

        assert result.exit_code == 0
        assert "No audio files found" in result.stdout

    def test_organize_by_format_filename_conflict(self, temp_music_dir, tmp_path):
        """Test organize handles filename conflicts."""
        from tests.conftest import create_test_mp3
        from mutagen.mp3 import MP3
        from mutagen.id3 import TIT2

        # Create two files with the same name in different directories
        dir1 = temp_music_dir / "dir1"
        dir2 = temp_music_dir / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        file1 = dir1 / "song.mp3"
        file2 = dir2 / "song.mp3"
        create_test_mp3(file1)
        create_test_mp3(file2)

        # Add tags so they're recognized
        for f in [file1, file2]:
            audio = MP3(str(f))
            audio["TIT2"] = TIT2(encoding=3, text="Test")
            audio.save()

        dest = tmp_path / "organized"

        result = runner.invoke(app, [
            "organize", "by-format",
            str(temp_music_dir),
            "--dest", str(dest),
            "--apply"
        ])

        assert result.exit_code == 0

        # Should have both files (one renamed to avoid conflict)
        mp3_files = list((dest / "MP3").glob("*.mp3"))
        assert len(mp3_files) == 2


class TestOrganizeBySamplerate:
    """Tests for 'musictl organize by-samplerate' command."""

    def test_organize_by_samplerate_dry_run(self, sample_flac_hires, tmp_path):
        """Test organize by-samplerate in dry-run mode."""
        result = runner.invoke(app, [
            "organize", "by-samplerate",
            str(sample_flac_hires.parent),
            "--dest", str(tmp_path / "hires")
        ])

        assert result.exit_code == 0
        assert "Dry run" in result.stdout
        assert "Hi-Res Files" in result.stdout
        # The 96kHz FLAC should be detected
        assert "hires.flac" in result.stdout or "96" in result.stdout
        # Destination should not be created in dry-run
        assert not (tmp_path / "hires").exists()

    def test_organize_by_samplerate_apply(self, sample_flac_hires, tmp_path):
        """Test organize by-samplerate with --apply."""
        dest = tmp_path / "hires"

        result = runner.invoke(app, [
            "organize", "by-samplerate",
            str(sample_flac_hires.parent),
            "--dest", str(dest),
            "--apply"
        ])

        assert result.exit_code == 0
        assert "Successfully moved" in result.stdout

        # Verify destination was created and file was moved
        assert dest.exists()
        hires_files = list(dest.glob("*.flac"))
        assert len(hires_files) == 1

    def test_organize_by_samplerate_custom_threshold(self, sample_mp3, tmp_path):
        """Test organize with custom threshold."""
        # Use a threshold lower than standard 44.1kHz
        result = runner.invoke(app, [
            "organize", "by-samplerate",
            str(sample_mp3.parent),
            "--dest", str(tmp_path / "hires"),
            "--threshold", "40000"
        ])

        assert result.exit_code == 0
        # 44.1kHz file should now be detected as hi-res
        assert "sample.mp3" in result.stdout or "44" in result.stdout

    def test_organize_by_samplerate_no_hires_files(self, sample_mp3, tmp_path):
        """Test organize when no hi-res files are found."""
        result = runner.invoke(app, [
            "organize", "by-samplerate",
            str(sample_mp3.parent),
            "--dest", str(tmp_path / "hires"),
            "--threshold", "48000"
        ])

        assert result.exit_code == 0
        # 44.1kHz file should not be considered hi-res
        assert "No files above" in result.stdout

    def test_organize_by_samplerate_missing_dest(self, sample_flac_hires):
        """Test organize without --dest flag."""
        result = runner.invoke(app, [
            "organize", "by-samplerate",
            str(sample_flac_hires.parent)
        ])

        # Should fail - dest is required
        assert result.exit_code != 0

    def test_organize_by_samplerate_shows_stats(self, sample_flac_hires, sample_mp3, tmp_path):
        """Test that organize shows standard vs hi-res file counts."""
        # Put both files in same directory
        hires_dir = sample_flac_hires.parent
        import shutil
        shutil.copy(sample_mp3, hires_dir / "standard.mp3")

        result = runner.invoke(app, [
            "organize", "by-samplerate",
            str(hires_dir),
            "--dest", str(tmp_path / "hires")
        ])

        assert result.exit_code == 0
        assert "Files to move:" in result.stdout
        assert "Standard files" in result.stdout


class TestOrganizeCommandsEdgeCases:
    """Edge case tests for organize commands."""

    def test_organize_no_subcommand(self):
        """Test running 'musictl organize' without subcommand."""
        result = runner.invoke(app, ["organize"])

        # Typer exits with code 2 when subcommand is missing
        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "Missing command" in output

    def test_organize_help(self):
        """Test 'musictl organize --help'."""
        result = runner.invoke(app, ["organize", "--help"])

        assert result.exit_code == 0
        assert "File organization" in result.stdout or "organization" in result.stdout.lower()
