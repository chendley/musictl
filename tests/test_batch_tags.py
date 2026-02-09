"""Integration tests for batch tag editing commands (set, clear)."""

from pathlib import Path

import pytest
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.id3 import TIT2, TPE1, TALB
from typer.testing import CliRunner

from musictl.cli import app
from tests.conftest import create_test_mp3, create_test_flac

runner = CliRunner()


@pytest.fixture
def mp3_with_partial_tags(temp_music_dir):
    """Create MP3s where some have tags and some don't."""
    files = []
    for i in range(3):
        mp3_path = temp_music_dir / f"song_{i}.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text=f"Song {i}")
        if i == 0:
            audio["TPE1"] = TPE1(encoding=3, text="Existing Artist")
            audio["TALB"] = TALB(encoding=3, text="Existing Album")
        audio.save()
        files.append(mp3_path)
    return temp_music_dir, files


@pytest.fixture
def flac_no_tags(temp_music_dir):
    """Create a FLAC file with no tags."""
    flac_path = temp_music_dir / "empty.flac"
    create_test_flac(flac_path)
    return flac_path


class TestTagsSet:
    def test_set_dry_run(self, mp3_with_partial_tags):
        music_dir, files = mp3_with_partial_tags
        result = runner.invoke(app, [
            "tags", "set", str(music_dir), "--artist", "New Artist",
        ])
        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert "would be updated" in result.output

        # Verify nothing changed
        audio = MP3(str(files[0]))
        assert str(audio["TPE1"]) == "Existing Artist"

    def test_set_apply(self, mp3_with_partial_tags):
        music_dir, files = mp3_with_partial_tags
        result = runner.invoke(app, [
            "tags", "set", str(music_dir), "--genre", "Rock", "--apply",
        ])
        assert result.exit_code == 0
        assert "Set tags in 3 files" in result.output

        # Verify all files got the genre
        for f in files:
            audio = MP3(str(f))
            assert "TCON" in audio

    def test_set_multiple_tags(self, mp3_with_partial_tags):
        music_dir, files = mp3_with_partial_tags
        result = runner.invoke(app, [
            "tags", "set", str(music_dir),
            "--artist", "Band", "--album", "Album", "--year", "2020",
            "--apply",
        ])
        assert result.exit_code == 0

        # File 0 already had artist, should be skipped
        audio = MP3(str(files[0]))
        assert str(audio["TPE1"]) == "Existing Artist"
        assert "TDRC" in audio

        # File 1 had no artist, should be set
        audio = MP3(str(files[1]))
        assert str(audio["TPE1"]) == "Band"

    def test_set_custom_tag(self, sample_flac):
        result = runner.invoke(app, [
            "tags", "set", str(sample_flac),
            "--tag", "genre=Electronic", "--apply",
        ])
        assert result.exit_code == 0

        audio = FLAC(str(sample_flac))
        assert audio["GENRE"] == ["Electronic"]

    def test_set_skip_existing_without_overwrite(self, mp3_with_partial_tags):
        music_dir, files = mp3_with_partial_tags
        result = runner.invoke(app, [
            "tags", "set", str(music_dir), "--artist", "New Artist", "--apply",
        ])
        assert result.exit_code == 0

        # File 0 should keep its original artist
        audio = MP3(str(files[0]))
        assert str(audio["TPE1"]) == "Existing Artist"

        # Files 1-2 should get the new artist
        audio = MP3(str(files[1]))
        assert str(audio["TPE1"]) == "New Artist"

    def test_set_overwrite_existing(self, mp3_with_partial_tags):
        music_dir, files = mp3_with_partial_tags
        result = runner.invoke(app, [
            "tags", "set", str(music_dir),
            "--artist", "Replaced", "--overwrite", "--apply",
        ])
        assert result.exit_code == 0

        # File 0 should now have the replaced artist
        audio = MP3(str(files[0]))
        assert str(audio["TPE1"]) == "Replaced"

    def test_set_directory_recursive(self, sample_library):
        music_dir, files = sample_library
        result = runner.invoke(app, [
            "tags", "set", str(music_dir), "--genre", "Test Genre", "--apply",
        ])
        assert result.exit_code == 0
        assert "Set tags in 5 files" in result.output

    def test_set_flac(self, flac_no_tags):
        result = runner.invoke(app, [
            "tags", "set", str(flac_no_tags),
            "--artist", "FLAC Artist", "--title", "FLAC Song", "--apply",
        ])
        assert result.exit_code == 0

        audio = FLAC(str(flac_no_tags))
        assert audio["ARTIST"] == ["FLAC Artist"]
        assert audio["TITLE"] == ["FLAC Song"]

    def test_set_no_tags_error(self, sample_mp3):
        result = runner.invoke(app, ["tags", "set", str(sample_mp3)])
        assert result.exit_code == 1
        assert "No tags specified" in result.output

    def test_set_invalid_tag_format(self, sample_mp3):
        result = runner.invoke(app, [
            "tags", "set", str(sample_mp3), "--tag", "notequals",
        ])
        assert result.exit_code == 1
        assert "expected key=value" in result.output

    def test_set_nonexistent_path(self):
        result = runner.invoke(app, [
            "tags", "set", "/nonexistent/path", "--artist", "Test",
        ])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestTagsClear:
    def test_clear_dry_run(self, sample_mp3):
        result = runner.invoke(app, [
            "tags", "clear", str(sample_mp3), "--tag", "artist",
        ])
        assert result.exit_code == 0
        assert "Dry run" in result.output

        # Verify tag still exists
        audio = MP3(str(sample_mp3))
        assert "TPE1" in audio

    def test_clear_apply(self, sample_mp3):
        result = runner.invoke(app, [
            "tags", "clear", str(sample_mp3), "--tag", "artist", "--apply",
        ])
        assert result.exit_code == 0
        assert "Cleared tags from 1 files" in result.output

        audio = MP3(str(sample_mp3))
        assert "TPE1" not in audio

    def test_clear_multiple_tags(self, sample_mp3):
        result = runner.invoke(app, [
            "tags", "clear", str(sample_mp3),
            "--tag", "artist", "--tag", "album", "--apply",
        ])
        assert result.exit_code == 0

        audio = MP3(str(sample_mp3))
        assert "TPE1" not in audio
        assert "TALB" not in audio
        # Title should still be there
        assert "TIT2" in audio

    def test_clear_nonexistent_tag(self, sample_mp3):
        result = runner.invoke(app, [
            "tags", "clear", str(sample_mp3), "--tag", "lyrics",
        ])
        assert result.exit_code == 0
        assert "had none of the specified tags" in result.output

    def test_clear_directory(self, sample_library):
        music_dir, files = sample_library
        result = runner.invoke(app, [
            "tags", "clear", str(music_dir), "--tag", "artist", "--apply",
        ])
        assert result.exit_code == 0
        assert "Cleared tags from 5 files" in result.output
