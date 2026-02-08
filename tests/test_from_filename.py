"""Integration tests for 'musictl tags from-filename' command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner
from mutagen.mp3 import MP3
from mutagen.id3 import TIT2, TPE1, TALB, TRCK
from mutagen.flac import FLAC

from musictl.cli import app
from tests.conftest import create_test_mp3, create_test_flac

runner = CliRunner()


@pytest.fixture
def named_mp3s(temp_music_dir):
    """Create MP3s with artist-title naming convention."""
    files = []
    names = [
        "Pink Floyd - Wish You Were Here.mp3",
        "Led Zeppelin - Stairway to Heaven.mp3",
        "Queen - Bohemian Rhapsody.mp3",
    ]
    for name in names:
        mp3_path = temp_music_dir / name
        create_test_mp3(mp3_path)
        files.append(mp3_path)
    return temp_music_dir, files


@pytest.fixture
def numbered_mp3s(temp_music_dir):
    """Create MP3s with track-title naming convention."""
    files = []
    names = [
        "01. First Song.mp3",
        "02. Second Song.mp3",
        "03. Third Song.mp3",
    ]
    for name in names:
        mp3_path = temp_music_dir / name
        create_test_mp3(mp3_path)
        files.append(mp3_path)
    return temp_music_dir, files


@pytest.fixture
def tagged_mp3s(temp_music_dir):
    """Create MP3s that already have tags."""
    files = []
    names = ["Artist - New Title.mp3"]
    for name in names:
        mp3_path = temp_music_dir / name
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text="Existing Title")
        audio["TPE1"] = TPE1(encoding=3, text="Existing Artist")
        audio.save()
        files.append(mp3_path)
    return temp_music_dir, files


@pytest.fixture
def named_flacs(temp_music_dir):
    """Create FLACs with artist-title naming convention."""
    files = []
    names = [
        "Bjork - Joga.flac",
        "Radiohead - Creep.flac",
    ]
    for name in names:
        flac_path = temp_music_dir / name
        create_test_flac(flac_path)
        files.append(flac_path)
    return temp_music_dir, files


@pytest.fixture
def non_matching_mp3s(temp_music_dir):
    """Create MP3s that don't match the pattern."""
    files = []
    names = [
        "JustAFilename.mp3",
        "no_separator_here.mp3",
    ]
    for name in names:
        mp3_path = temp_music_dir / name
        create_test_mp3(mp3_path)
        files.append(mp3_path)
    return temp_music_dir, files


class TestFromFilenameDryRun:
    """Test dry-run mode (default behavior)."""

    def test_dry_run_shows_preview(self, named_mp3s):
        """Dry-run shows what tags would be set."""
        music_dir, _ = named_mp3s
        result = runner.invoke(app, [
            "tags", "from-filename", str(music_dir),
            "-p", "{artist} - {title}",
        ])

        assert result.exit_code == 0
        assert "Pink Floyd" in result.stdout
        assert "Wish You Were Here" in result.stdout
        assert "Dry run" in result.stdout
        assert "3 files would be updated" in result.stdout

    def test_dry_run_does_not_modify_files(self, named_mp3s):
        """Dry-run must not write any tags."""
        music_dir, files = named_mp3s
        runner.invoke(app, [
            "tags", "from-filename", str(music_dir),
            "-p", "{artist} - {title}",
        ])

        # Verify no tags were written
        for f in files:
            audio = MP3(str(f))
            assert audio.tags is None or len(audio.tags) <= 1  # only TSSE from ffmpeg

    def test_dry_run_with_track_pattern(self, numbered_mp3s):
        """Dry-run with track number pattern."""
        music_dir, _ = numbered_mp3s
        result = runner.invoke(app, [
            "tags", "from-filename", str(music_dir),
            "-p", "{track}. {title}",
        ])

        assert result.exit_code == 0
        assert "First Song" in result.stdout
        assert "Second Song" in result.stdout
        assert "tracknumber" in result.stdout
        assert "Dry run" in result.stdout


class TestFromFilenameApply:
    """Test applying tags."""

    def test_apply_writes_tags(self, named_mp3s):
        """Apply mode writes correct tags to files."""
        music_dir, files = named_mp3s
        result = runner.invoke(app, [
            "tags", "from-filename", str(music_dir),
            "-p", "{artist} - {title}",
            "--apply",
        ])

        assert result.exit_code == 0
        assert "Updated: 3 files" in result.stdout

        # Verify tags were written correctly
        audio = MP3(str(files[0]))  # Pink Floyd
        assert str(audio["TIT2"]) == "Wish You Were Here"
        assert str(audio["TPE1"]) == "Pink Floyd"

        audio = MP3(str(files[2]))  # Queen
        assert str(audio["TIT2"]) == "Bohemian Rhapsody"
        assert str(audio["TPE1"]) == "Queen"

    def test_apply_track_numbers(self, numbered_mp3s):
        """Apply mode writes track numbers correctly."""
        music_dir, files = numbered_mp3s
        result = runner.invoke(app, [
            "tags", "from-filename", str(music_dir),
            "-p", "{track}. {title}",
            "--apply",
        ])

        assert result.exit_code == 0

        audio = MP3(str(files[0]))  # 01. First Song
        assert str(audio["TIT2"]) == "First Song"
        assert str(audio["TRCK"]) == "1"

        audio = MP3(str(files[2]))  # 03. Third Song
        assert str(audio["TIT2"]) == "Third Song"
        assert str(audio["TRCK"]) == "3"

    def test_apply_flac_files(self, named_flacs):
        """Apply mode works with FLAC files."""
        music_dir, files = named_flacs
        result = runner.invoke(app, [
            "tags", "from-filename", str(music_dir),
            "-p", "{artist} - {title}",
            "--apply",
        ])

        assert result.exit_code == 0

        audio = FLAC(str(files[0]))  # Bjork
        assert audio["title"] == ["Joga"]
        assert audio["artist"] == ["Bjork"]

        audio = FLAC(str(files[1]))  # Radiohead
        assert audio["title"] == ["Creep"]
        assert audio["artist"] == ["Radiohead"]


class TestFromFilenameOverwrite:
    """Test overwrite behavior."""

    def test_skips_existing_tags_by_default(self, tagged_mp3s):
        """Without --overwrite, existing tags are preserved."""
        music_dir, files = tagged_mp3s
        result = runner.invoke(app, [
            "tags", "from-filename", str(music_dir),
            "-p", "{artist} - {title}",
            "--apply",
        ])

        assert result.exit_code == 0

        # Tags should be unchanged
        audio = MP3(str(files[0]))
        assert str(audio["TIT2"]) == "Existing Title"
        assert str(audio["TPE1"]) == "Existing Artist"

    def test_overwrite_replaces_existing_tags(self, tagged_mp3s):
        """With --overwrite, existing tags are replaced."""
        music_dir, files = tagged_mp3s
        result = runner.invoke(app, [
            "tags", "from-filename", str(music_dir),
            "-p", "{artist} - {title}",
            "--apply", "--overwrite",
        ])

        assert result.exit_code == 0

        audio = MP3(str(files[0]))
        assert str(audio["TIT2"]) == "New Title"
        assert str(audio["TPE1"]) == "Artist"


class TestFromFilenameNoMatch:
    """Test files that don't match the pattern."""

    def test_non_matching_files_skipped(self, non_matching_mp3s):
        """Files that don't match the pattern are skipped."""
        music_dir, _ = non_matching_mp3s
        result = runner.invoke(app, [
            "tags", "from-filename", str(music_dir),
            "-p", "{artist} - {title}",
        ])

        assert result.exit_code == 0
        assert "Skipped (no match)" in result.stdout
        assert "0 files would be updated" in result.stdout

    def test_mixed_matching_and_non_matching(self, temp_music_dir):
        """Mix of matching and non-matching files."""
        # Create one matching and one non-matching
        matching = temp_music_dir / "Artist - Title.mp3"
        create_test_mp3(matching)
        non_matching = temp_music_dir / "random_name.mp3"
        create_test_mp3(non_matching)

        result = runner.invoke(app, [
            "tags", "from-filename", str(temp_music_dir),
            "-p", "{artist} - {title}",
        ])

        assert result.exit_code == 0
        assert "Matched pattern: 1 files" in result.stdout
        assert "Skipped (no match): 1 files" in result.stdout


class TestFromFilenameErrorHandling:
    """Test error conditions."""

    def test_nonexistent_path(self):
        """Nonexistent path gives clear error."""
        result = runner.invoke(app, [
            "tags", "from-filename", "/nonexistent/path",
            "-p", "{artist} - {title}",
        ])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_invalid_pattern(self, temp_music_dir):
        """Invalid field name in pattern gives clear error."""
        result = runner.invoke(app, [
            "tags", "from-filename", str(temp_music_dir),
            "-p", "{artist} - {bogus}",
        ])

        assert result.exit_code == 1
        assert "Unknown field" in result.stdout

    def test_no_audio_files(self, temp_music_dir):
        """Directory with no audio files."""
        result = runner.invoke(app, [
            "tags", "from-filename", str(temp_music_dir),
            "-p", "{artist} - {title}",
        ])

        assert result.exit_code == 0
        assert "No audio files found" in result.stdout

    def test_pattern_required(self, temp_music_dir):
        """Pattern option is required."""
        result = runner.invoke(app, [
            "tags", "from-filename", str(temp_music_dir),
        ])

        assert result.exit_code != 0


class TestFromFilenameIdempotent:
    """Test that running twice produces the same result."""

    def test_second_run_no_changes(self, named_mp3s):
        """Running twice: second run should find nothing to update."""
        music_dir, _ = named_mp3s

        # First run - apply
        result1 = runner.invoke(app, [
            "tags", "from-filename", str(music_dir),
            "-p", "{artist} - {title}",
            "--apply",
        ])
        assert result1.exit_code == 0
        assert "Updated: 3 files" in result1.stdout

        # Second run - should find nothing to do
        result2 = runner.invoke(app, [
            "tags", "from-filename", str(music_dir),
            "-p", "{artist} - {title}",
        ])
        assert result2.exit_code == 0
        assert "0 files would be updated" in result2.stdout
