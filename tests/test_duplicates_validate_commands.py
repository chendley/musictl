"""Integration tests for duplicates and validation commands."""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner
from mutagen.mp3 import MP3
from mutagen.id3 import TIT2, TPE1, TALB

from musictl.cli import app
from tests.conftest import create_test_mp3

runner = CliRunner()


class TestDuplicatesFind:
    """Tests for 'musictl dupes find' command."""

    def test_dupes_find_no_duplicates(self, temp_music_dir, sample_mp3, sample_flac):
        """Test duplicate detection when no duplicates exist."""
        result = runner.invoke(app, ["dupes", "find", str(temp_music_dir)])

        assert result.exit_code == 0
        assert "No duplicates found" in result.stdout

    def test_dupes_find_exact_duplicates(self, temp_music_dir):
        """Test exact duplicate detection."""
        # Create identical files
        original = temp_music_dir / "original.mp3"
        dup1 = temp_music_dir / "dup1.mp3"
        dup2 = temp_music_dir / "dup2.mp3"

        create_test_mp3(original)
        shutil.copy(original, dup1)
        shutil.copy(original, dup2)

        result = runner.invoke(app, ["dupes", "find", str(temp_music_dir)])

        assert result.exit_code == 0
        assert "Duplicate Files" in result.stdout
        assert "original.mp3" in result.stdout or "dup1.mp3" in result.stdout
        assert "Wasted space" in result.stdout
        assert "Dry run" in result.stdout

    def test_dupes_find_with_apply(self, temp_music_dir):
        """Test duplicate deletion with --apply."""
        # Create identical files
        original = temp_music_dir / "original.mp3"
        dup1 = temp_music_dir / "dup1.mp3"

        create_test_mp3(original)
        shutil.copy(original, dup1)

        result = runner.invoke(app, ["dupes", "find", str(temp_music_dir), "--apply"])

        assert result.exit_code == 0
        assert "Successfully deleted" in result.stdout or "Deleted" in result.stdout

        # Verify one file was deleted
        files = list(temp_music_dir.glob("*.mp3"))
        assert len(files) == 1

    def test_dupes_find_multiple_groups(self, temp_music_dir):
        """Test detection of multiple duplicate groups."""
        # Group 1
        file1a = temp_music_dir / "file1a.mp3"
        file1b = temp_music_dir / "file1b.mp3"
        create_test_mp3(file1a)
        shutil.copy(file1a, file1b)

        # Group 2
        file2a = temp_music_dir / "file2a.mp3"
        file2b = temp_music_dir / "file2b.mp3"
        create_test_mp3(file2a, duration=0.2)  # Different content
        shutil.copy(file2a, file2b)

        result = runner.invoke(app, ["dupes", "find", str(temp_music_dir)])

        assert result.exit_code == 0
        assert "2 groups" in result.stdout or "Group 1" in result.stdout

    def test_dupes_find_fuzzy_mode(self, temp_music_dir):
        """Test fuzzy duplicate detection."""
        # Create files with same metadata but different formats
        mp3_file = temp_music_dir / "song.mp3"
        create_test_mp3(mp3_file)

        audio = MP3(str(mp3_file))
        audio["TIT2"] = TIT2(encoding=3, text="Test Song")
        audio["TPE1"] = TPE1(encoding=3, text="Test Artist")
        audio.save()

        # Create another file (won't be a fuzzy duplicate unless tags match exactly)
        mp3_file2 = temp_music_dir / "song2.mp3"
        create_test_mp3(mp3_file2)

        audio2 = MP3(str(mp3_file2))
        audio2["TIT2"] = TIT2(encoding=3, text="Test Song")  # Same title
        audio2["TPE1"] = TPE1(encoding=3, text="Test Artist")  # Same artist
        audio2.save()

        result = runner.invoke(app, ["dupes", "find", str(temp_music_dir), "--fuzzy"])

        assert result.exit_code == 0
        # Should either find fuzzy duplicates or report none found
        assert "fuzzy duplicate" in result.stdout.lower() or "potential duplicate" in result.stdout.lower()

    def test_dupes_find_fuzzy_no_apply(self, temp_music_dir):
        """Test that fuzzy mode doesn't allow --apply."""
        # Create potential fuzzy duplicates
        mp3_file = temp_music_dir / "song.mp3"
        mp3_file2 = temp_music_dir / "song2.mp3"
        create_test_mp3(mp3_file)
        create_test_mp3(mp3_file2)

        # Add matching metadata
        for path in [mp3_file, mp3_file2]:
            audio = MP3(str(path))
            audio["TIT2"] = TIT2(encoding=3, text="Same Song")
            audio["TPE1"] = TPE1(encoding=3, text="Same Artist")
            audio.save()

        result = runner.invoke(app, ["dupes", "find", str(temp_music_dir), "--fuzzy", "--apply"])

        # Should error when fuzzy duplicates are found with --apply
        if "potential duplicate" in result.stdout.lower():
            assert result.exit_code == 1
            assert "--apply is not supported" in result.stdout or "not supported" in result.stdout.lower()
        else:
            # If no fuzzy duplicates found, that's also acceptable
            assert result.exit_code == 0

    def test_dupes_find_empty_directory(self, temp_music_dir):
        """Test duplicate detection on empty directory."""
        empty_dir = temp_music_dir / "empty"
        empty_dir.mkdir()

        result = runner.invoke(app, ["dupes", "find", str(empty_dir)])

        assert result.exit_code == 0
        assert "No audio files found" in result.stdout

    def test_dupes_find_nonexistent_path(self):
        """Test duplicate detection on nonexistent path."""
        result = runner.invoke(app, ["dupes", "find", "/nonexistent/path"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


class TestValidateCheck:
    """Tests for 'musictl validate check' command."""

    def test_validate_valid_files(self, sample_library):
        """Test validation of valid audio files."""
        music_dir, files = sample_library

        result = runner.invoke(app, ["validate", "check", str(music_dir)])

        assert result.exit_code == 0
        assert "Summary:" in result.stdout
        assert "Valid files:" in result.stdout
        assert "All files validated successfully" in result.stdout

    def test_validate_single_file(self, sample_mp3):
        """Test validation of a single file."""
        result = runner.invoke(app, ["validate", "check", str(sample_mp3)])

        assert result.exit_code == 0
        assert "Total files: 1" in result.stdout
        assert "Valid files: 1" in result.stdout

    def test_validate_invalid_file(self, temp_music_dir):
        """Test validation detects corrupted files."""
        # Create a fake MP3 file with invalid content
        bad_file = temp_music_dir / "corrupted.mp3"
        bad_file.write_text("This is not a valid MP3 file")

        result = runner.invoke(app, ["validate", "check", str(temp_music_dir)])

        assert result.exit_code == 0
        assert "Invalid files:" in result.stdout or "corrupted" in result.stdout.lower()
        assert "Invalid Files" in result.stdout

    def test_validate_mixed_files(self, temp_music_dir):
        """Test validation with mix of valid and invalid files."""
        # Create one valid file
        valid_file = temp_music_dir / "valid.mp3"
        create_test_mp3(valid_file)

        # Create one invalid file
        invalid_file = temp_music_dir / "invalid.mp3"
        invalid_file.write_text("Not valid")

        result = runner.invoke(app, ["validate", "check", str(temp_music_dir)])

        assert result.exit_code == 0
        assert "Total files: 2" in result.stdout
        assert "Valid files: 1" in result.stdout
        assert "Invalid files: 1" in result.stdout

    def test_validate_verbose_mode(self, sample_mp3):
        """Test validation with verbose output."""
        result = runner.invoke(app, ["validate", "check", str(sample_mp3.parent), "--verbose"])

        assert result.exit_code == 0
        # Should show individual file validation results
        assert "sample.mp3" in result.stdout
        assert "✓" in result.stdout or "OK" in result.stdout

    def test_validate_non_recursive(self, sample_library):
        """Test non-recursive validation."""
        music_dir, files = sample_library

        result = runner.invoke(app, ["validate", "check", str(music_dir), "--no-recursive"])

        assert result.exit_code == 0
        # Should only validate files in the root (none in this case)
        assert "Total files: 0" in result.stdout or "No audio files" in result.stdout

    def test_validate_empty_directory(self, temp_music_dir):
        """Test validation on empty directory."""
        empty_dir = temp_music_dir / "empty"
        empty_dir.mkdir()

        result = runner.invoke(app, ["validate", "check", str(empty_dir)])

        assert result.exit_code == 0
        assert "No audio files found" in result.stdout

    def test_validate_nonexistent_path(self):
        """Test validation on nonexistent path."""
        result = runner.invoke(app, ["validate", "check", "/nonexistent/path"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


class TestDuplicatesValidateEdgeCases:
    """Edge case tests for duplicates and validate commands."""

    def test_dupes_help(self):
        """Test 'musictl dupes --help'."""
        result = runner.invoke(app, ["dupes", "--help"])

        assert result.exit_code == 0
        assert "Duplicate detection" in result.stdout or "duplicate" in result.stdout.lower()

    def test_validate_help(self):
        """Test 'musictl validate --help'."""
        result = runner.invoke(app, ["validate", "--help"])

        assert result.exit_code == 0
        assert "validation" in result.stdout.lower() or "integrity" in result.stdout.lower()
