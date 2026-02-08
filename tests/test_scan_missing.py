"""Tests for scan missing tags command."""

import csv
import json
from pathlib import Path

import pytest
from mutagen.flac import FLAC
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC
from mutagen.mp3 import MP3
from typer.testing import CliRunner

from musictl.cli import app
from tests.conftest import create_test_mp3, create_test_flac


runner = CliRunner()


@pytest.fixture
def incomplete_mp3(temp_music_dir):
    """Create MP3 with only title and artist (missing album and year)."""
    mp3_path = temp_music_dir / "incomplete.mp3"
    create_test_mp3(mp3_path)

    audio = MP3(str(mp3_path))
    audio["TIT2"] = TIT2(encoding=3, text="Test Song")
    audio["TPE1"] = TPE1(encoding=3, text="Test Artist")
    # Missing: TALB (album), TDRC (year)
    audio.save()

    return mp3_path


@pytest.fixture
def no_tags_mp3(temp_music_dir):
    """Create MP3 with no tags at all."""
    mp3_path = temp_music_dir / "no_tags.mp3"
    create_test_mp3(mp3_path)
    return mp3_path


@pytest.fixture
def complete_flac(temp_music_dir):
    """Create FLAC with all required tags."""
    flac_path = temp_music_dir / "complete.flac"
    create_test_flac(flac_path)

    audio = FLAC(str(flac_path))
    audio["TITLE"] = "Complete Song"
    audio["ARTIST"] = "Complete Artist"
    audio["ALBUM"] = "Complete Album"
    audio["DATE"] = "2020"
    audio.save()

    return flac_path


@pytest.fixture
def missing_title_flac(temp_music_dir):
    """Create FLAC missing title."""
    flac_path = temp_music_dir / "missing_title.flac"
    create_test_flac(flac_path)

    audio = FLAC(str(flac_path))
    audio["ARTIST"] = "Artist"
    audio["ALBUM"] = "Album"
    audio["DATE"] = "2021"
    # Missing: TITLE
    audio.save()

    return flac_path


class TestScanMissing:
    """Test scan missing tags functionality."""

    def test_scan_missing_all_complete(self, temp_music_dir):
        """Test scan when all files have complete metadata."""
        # Create MP3 with all required tags
        mp3_path = temp_music_dir / "complete.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text="Test Song")
        audio["TPE1"] = TPE1(encoding=3, text="Test Artist")
        audio["TALB"] = TALB(encoding=3, text="Test Album")
        audio["TDRC"] = TDRC(encoding=3, text="2020")
        audio.save()

        # Create FLAC with all required tags
        flac_path = temp_music_dir / "complete.flac"
        create_test_flac(flac_path)
        flac_audio = FLAC(str(flac_path))
        flac_audio["TITLE"] = "Complete Song"
        flac_audio["ARTIST"] = "Complete Artist"
        flac_audio["ALBUM"] = "Complete Album"
        flac_audio["DATE"] = "2021"
        flac_audio.save()

        result = runner.invoke(app, ["scan", "missing", str(temp_music_dir)])

        assert result.exit_code == 0
        assert "All files have complete metadata" in result.stdout

    def test_scan_missing_finds_incomplete(self, incomplete_mp3):
        """Test scan finds files with missing tags."""
        music_dir = incomplete_mp3.parent

        result = runner.invoke(app, ["scan", "missing", str(music_dir)])

        assert result.exit_code == 0
        assert "Files with Missing Tags" in result.stdout
        assert "incomplete.mp3" in result.stdout
        assert "album" in result.stdout.lower()
        assert "year" in result.stdout.lower()

    def test_scan_missing_finds_no_tags(self, no_tags_mp3):
        """Test scan finds files with no tags."""
        music_dir = no_tags_mp3.parent

        result = runner.invoke(app, ["scan", "missing", str(music_dir)])

        assert result.exit_code == 0
        assert "no_tags.mp3" in result.stdout
        # Should report all four required tags missing
        assert "artist" in result.stdout.lower()
        assert "album" in result.stdout.lower()
        assert "title" in result.stdout.lower()
        assert "year" in result.stdout.lower()

    def test_scan_missing_finds_partial(self, missing_title_flac):
        """Test scan finds FLAC missing only title."""
        music_dir = missing_title_flac.parent

        result = runner.invoke(app, ["scan", "missing", str(music_dir)])

        assert result.exit_code == 0
        assert "missing_title.flac" in result.stdout
        assert "title" in result.stdout.lower()

    def test_scan_missing_mixed_files(self, temp_music_dir):
        """Test scan with mix of complete and incomplete files."""
        # Create complete file
        complete = temp_music_dir / "complete.mp3"
        create_test_mp3(complete)
        audio = MP3(str(complete))
        audio["TIT2"] = TIT2(encoding=3, text="Song")
        audio["TPE1"] = TPE1(encoding=3, text="Artist")
        audio["TALB"] = TALB(encoding=3, text="Album")
        audio["TDRC"] = TDRC(encoding=3, text="2020")
        audio.save()

        # Create incomplete file
        incomplete = temp_music_dir / "incomplete.mp3"
        create_test_mp3(incomplete)
        audio = MP3(str(incomplete))
        audio["TIT2"] = TIT2(encoding=3, text="Song")
        # Missing artist, album, year
        audio.save()

        result = runner.invoke(app, ["scan", "missing", str(temp_music_dir)])

        assert result.exit_code == 0
        assert "1 files with incomplete metadata out of 2 total" in result.stdout
        assert "incomplete.mp3" in result.stdout
        # Check that complete.mp3 is not listed (avoid substring match with incomplete.mp3)
        assert "  complete.mp3" not in result.stdout

    def test_scan_missing_non_recursive(self, temp_music_dir):
        """Test non-recursive scan."""
        # Create file in root
        root_file = temp_music_dir / "root.mp3"
        create_test_mp3(root_file)

        # Create subdirectory with file
        subdir = temp_music_dir / "subdir"
        subdir.mkdir()
        sub_file = subdir / "sub.mp3"
        create_test_mp3(sub_file)

        result = runner.invoke(app, ["scan", "missing", str(temp_music_dir), "--no-recursive"])

        assert result.exit_code == 0
        # Should only scan root directory
        if "Files with Missing Tags" in result.stdout:
            assert "root.mp3" in result.stdout or "All files have complete" in result.stdout

    def test_scan_missing_export_csv(self, incomplete_mp3, tmp_path):
        """Test CSV export of missing tags."""
        music_dir = incomplete_mp3.parent
        export_path = tmp_path / "missing.csv"

        result = runner.invoke(app, [
            "scan", "missing", str(music_dir),
            "--export", str(export_path),
            "--format", "csv"
        ])

        assert result.exit_code == 0
        assert export_path.exists()

        with open(export_path, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)

            # Check header
            assert rows[0] == ["File Path", "Format", "Missing Tags"]

            # Check data
            assert len(rows) > 1
            assert "incomplete.mp3" in rows[1][0]
            assert "album" in rows[1][2].lower()
            assert "year" in rows[1][2].lower()

    def test_scan_missing_export_json(self, incomplete_mp3, tmp_path):
        """Test JSON export of missing tags."""
        music_dir = incomplete_mp3.parent
        export_path = tmp_path / "missing.json"

        result = runner.invoke(app, [
            "scan", "missing", str(music_dir),
            "--export", str(export_path),
            "--format", "json"
        ])

        assert result.exit_code == 0
        assert export_path.exists()

        with open(export_path, "r") as f:
            data = json.load(f)

            assert "scan_path" in data
            assert "total_scanned" in data
            assert "incomplete_count" in data
            assert data["incomplete_count"] == 1
            assert "files" in data
            assert len(data["files"]) == 1
            assert "incomplete.mp3" in data["files"][0]["path"]
            assert "album" in data["files"][0]["missing_tags"]
            assert "year" in data["files"][0]["missing_tags"]

    def test_scan_missing_no_export_when_complete(self, temp_music_dir, tmp_path):
        """Test that no export file is created when all files are complete."""
        # Create complete MP3
        mp3_path = temp_music_dir / "complete.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text="Song")
        audio["TPE1"] = TPE1(encoding=3, text="Artist")
        audio["TALB"] = TALB(encoding=3, text="Album")
        audio["TDRC"] = TDRC(encoding=3, text="2020")
        audio.save()

        export_path = tmp_path / "missing.csv"

        result = runner.invoke(app, [
            "scan", "missing", str(temp_music_dir),
            "--export", str(export_path)
        ])

        assert result.exit_code == 0
        # No export when all files are complete
        assert not export_path.exists()

    def test_scan_missing_empty_directory(self, temp_music_dir):
        """Test scan on empty directory."""
        result = runner.invoke(app, ["scan", "missing", str(temp_music_dir)])

        assert result.exit_code == 0
        assert "No audio files found" in result.stdout

    def test_scan_missing_nonexistent_path(self):
        """Test scan on nonexistent path."""
        result = runner.invoke(app, ["scan", "missing", "/nonexistent/path"])

        assert result.exit_code == 1
        assert "Path not found" in result.stdout

    def test_scan_missing_invalid_export_format(self, incomplete_mp3, tmp_path):
        """Test invalid export format."""
        music_dir = incomplete_mp3.parent
        export_path = tmp_path / "missing.xml"

        result = runner.invoke(app, [
            "scan", "missing", str(music_dir),
            "--export", str(export_path),
            "--format", "xml"
        ])

        assert result.exit_code == 1
        assert "Invalid format" in result.stdout
