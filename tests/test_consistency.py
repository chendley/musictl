"""Integration tests for scan consistency command."""

from pathlib import Path

import pytest
from mutagen.id3 import TIT2, TPE1, TPE2, TALB, TRCK
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from typer.testing import CliRunner

from musictl.cli import app
from tests.conftest import create_test_mp3, create_test_flac

runner = CliRunner()


@pytest.fixture
def clean_album(tmp_path):
    """Album with consistent tags and correct numbering."""
    album = tmp_path / "Clean Album"
    album.mkdir()
    for i in range(5):
        mp3_path = album / f"track_{i+1}.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text=f"Song {i+1}")
        audio["TPE1"] = TPE1(encoding=3, text="Artist")
        audio["TALB"] = TALB(encoding=3, text="Album")
        audio["TRCK"] = TRCK(encoding=3, text=f"{i+1}/5")
        audio.save()
    return album


@pytest.fixture
def mismatched_album_names(tmp_path):
    """Album where files have different album tags."""
    album = tmp_path / "Mismatched"
    album.mkdir()
    for i, name in enumerate(["Album A", "Album A", "Album B"]):
        mp3_path = album / f"track_{i}.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text=f"Song {i}")
        audio["TPE1"] = TPE1(encoding=3, text="Artist")
        audio["TALB"] = TALB(encoding=3, text=name)
        audio["TRCK"] = TRCK(encoding=3, text=str(i + 1))
        audio.save()
    return album


@pytest.fixture
def mismatched_album_artist(tmp_path):
    """Album where files have different album artist tags."""
    album = tmp_path / "MismatchedAA"
    album.mkdir()
    for i, aa in enumerate(["AA One", "AA Two"]):
        mp3_path = album / f"track_{i}.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text=f"Song {i}")
        audio["TPE1"] = TPE1(encoding=3, text="Artist")
        audio["TPE2"] = TPE2(encoding=3, text=aa)
        audio["TALB"] = TALB(encoding=3, text="Album")
        audio["TRCK"] = TRCK(encoding=3, text=str(i + 1))
        audio.save()
    return album


@pytest.fixture
def missing_track_numbers(tmp_path):
    """Album where some files lack track numbers."""
    album = tmp_path / "NoTracks"
    album.mkdir()
    for i in range(3):
        mp3_path = album / f"track_{i}.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text=f"Song {i}")
        audio["TPE1"] = TPE1(encoding=3, text="Artist")
        audio["TALB"] = TALB(encoding=3, text="Album")
        if i == 0:
            audio["TRCK"] = TRCK(encoding=3, text="1")
        audio.save()
    return album


@pytest.fixture
def duplicate_tracks(tmp_path):
    """Album with duplicate track numbers."""
    album = tmp_path / "DupeTracks"
    album.mkdir()
    for i in range(3):
        mp3_path = album / f"track_{i}.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text=f"Song {i}")
        audio["TPE1"] = TPE1(encoding=3, text="Artist")
        audio["TALB"] = TALB(encoding=3, text="Album")
        # Two files claim to be track 1
        audio["TRCK"] = TRCK(encoding=3, text="1" if i < 2 else "2")
        audio.save()
    return album


@pytest.fixture
def track_gaps(tmp_path):
    """Album with gaps in track numbering."""
    album = tmp_path / "GapTracks"
    album.mkdir()
    for i, track_num in enumerate([1, 2, 5]):
        mp3_path = album / f"track_{i}.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text=f"Song {i}")
        audio["TPE1"] = TPE1(encoding=3, text="Artist")
        audio["TALB"] = TALB(encoding=3, text="Album")
        audio["TRCK"] = TRCK(encoding=3, text=str(track_num))
        audio.save()
    return album


@pytest.fixture
def missing_essential(tmp_path):
    """Album with files missing title/artist/album."""
    album = tmp_path / "Incomplete"
    album.mkdir()
    for i in range(2):
        mp3_path = album / f"track_{i}.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        if i == 0:
            audio["TIT2"] = TIT2(encoding=3, text="Song")
            audio["TPE1"] = TPE1(encoding=3, text="Artist")
            audio["TALB"] = TALB(encoding=3, text="Album")
        # File 1 has no tags at all
        audio.save()
    return album


class TestConsistency:
    def test_clean_album(self, clean_album):
        result = runner.invoke(app, ["scan", "consistency", str(clean_album)])
        assert result.exit_code == 0
        assert "0 with issues" in result.output

    def test_mismatched_album(self, mismatched_album_names):
        result = runner.invoke(app, ["scan", "consistency", str(mismatched_album_names)])
        assert result.exit_code == 0
        assert "Mismatched album" in result.output
        assert "'Album A'" in result.output
        assert "'Album B'" in result.output

    def test_mismatched_album_artist(self, mismatched_album_artist):
        result = runner.invoke(app, ["scan", "consistency", str(mismatched_album_artist)])
        assert result.exit_code == 0
        assert "Mismatched album artist" in result.output

    def test_missing_track_numbers(self, missing_track_numbers):
        result = runner.invoke(app, ["scan", "consistency", str(missing_track_numbers)])
        assert result.exit_code == 0
        assert "Missing track number: 2 files" in result.output

    def test_duplicate_tracks(self, duplicate_tracks):
        result = runner.invoke(app, ["scan", "consistency", str(duplicate_tracks)])
        assert result.exit_code == 0
        assert "Duplicate tracks" in result.output
        assert "#1 (2x)" in result.output

    def test_track_gaps(self, track_gaps):
        result = runner.invoke(app, ["scan", "consistency", str(track_gaps)])
        assert result.exit_code == 0
        assert "Track gaps" in result.output
        assert "3, 4" in result.output

    def test_missing_essential(self, missing_essential):
        result = runner.invoke(app, ["scan", "consistency", str(missing_essential)])
        assert result.exit_code == 0
        assert "Missing essential tags: 1 files" in result.output

    def test_summary_mode(self, mismatched_album_names):
        result = runner.invoke(app, [
            "scan", "consistency", str(mismatched_album_names), "--summary",
        ])
        assert result.exit_code == 0
        assert "1 with issues" in result.output
        # Should NOT show per-album details
        assert "Mismatched album" not in result.output

    def test_multiple_albums(self, clean_album, mismatched_album_names):
        # Scan parent directory containing both
        parent = clean_album.parent
        result = runner.invoke(app, ["scan", "consistency", str(parent)])
        assert result.exit_code == 0
        assert "2 albums checked" in result.output
        assert "1 with issues" in result.output

    def test_nonexistent_path(self):
        result = runner.invoke(app, ["scan", "consistency", "/nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
