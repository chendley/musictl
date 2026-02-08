"""Tests for strip-v1 safety features."""

import subprocess
from pathlib import Path

import pytest
from mutagen.id3 import ID3, TIT2, TPE1, TALB
from typer.testing import CliRunner

from musictl.cli import app


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


@pytest.fixture
def mp3_no_id3v2(tmp_path):
    """Create an MP3 file without any ID3v2 tags."""
    from mutagen.id3 import ID3, ID3NoHeaderError

    mp3_path = tmp_path / "test.mp3"
    # Create MP3
    subprocess.run(
        [
            "ffmpeg",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=mono",
            "-t", "0.1",
            "-q:a", "9",
            "-y",
            str(mp3_path),
        ],
        capture_output=True,
        check=True,
    )

    # Remove any ID3v2 header that ffmpeg added
    try:
        ID3(str(mp3_path)).delete(str(mp3_path))  # Delete the ID3v2 header completely
    except ID3NoHeaderError:
        pass  # No ID3v2 header, which is what we want

    return mp3_path


def add_id3v1_tag(mp3_path: Path):
    """Add a minimal ID3v1 tag to an MP3 file."""
    # ID3v1 tag structure: 128 bytes at end of file
    # TAG (3 bytes) + title (30) + artist (30) + album (30) + year (4) + comment (30) + genre (1)
    v1_tag = b"TAG"
    v1_tag += b"Test Title".ljust(30, b"\x00")
    v1_tag += b"Test Artist".ljust(30, b"\x00")
    v1_tag += b"Test Album".ljust(30, b"\x00")
    v1_tag += b"2024".ljust(4, b"\x00")
    v1_tag += b"Test Comment".ljust(30, b"\x00")
    v1_tag += b"\x00"  # Genre

    with open(mp3_path, "ab") as f:
        f.write(v1_tag)


def has_id3v1_tag(mp3_path: Path) -> bool:
    """Check if file has ID3v1 tag."""
    try:
        with open(mp3_path, "rb") as f:
            f.seek(-128, 2)
            return f.read(3) == b"TAG"
    except Exception:
        return False


def test_strip_v1_default_skips_v1_only(runner, mp3_no_id3v2):
    """Test that strip-v1 skips files with only ID3v1 tags by default."""
    # Add ID3v1 tag (no ID3v2)
    add_id3v1_tag(mp3_no_id3v2)

    result = runner.invoke(app, ["tags", "strip-v1", str(mp3_no_id3v2), "--apply"])

    assert result.exit_code == 0
    assert "Skipped 1 files with only ID3v1 tags" in result.stdout
    # ID3v1 should still be there
    assert has_id3v1_tag(mp3_no_id3v2)


def test_strip_v1_strips_when_v2_exists(runner, mp3_no_id3v2):
    """Test that strip-v1 works when ID3v2 tags exist."""
    # Add ID3v2 tags
    id3 = ID3()
    id3.add(TIT2(encoding=3, text="Test"))
    id3.save(str(mp3_no_id3v2))

    # Add ID3v1 tag
    add_id3v1_tag(mp3_no_id3v2)

    result = runner.invoke(app, ["tags", "strip-v1", str(mp3_no_id3v2), "--apply"])

    assert result.exit_code == 0
    assert "Stripped ID3v1 from 1 files" in result.stdout
    # ID3v1 should be gone
    assert not has_id3v1_tag(mp3_no_id3v2)
    # ID3v2 should still exist
    id3 = ID3(str(mp3_no_id3v2))
    assert "TIT2" in id3


def test_strip_v1_migrate_copies_to_v2(runner, mp3_no_id3v2):
    """Test that --migrate copies ID3v1 data to ID3v2 before stripping."""
    # Add ID3v1 tag only
    add_id3v1_tag(mp3_no_id3v2)

    result = runner.invoke(app, ["tags", "strip-v1", str(mp3_no_id3v2), "--apply", "--migrate"])

    assert result.exit_code == 0
    assert "Migrated 1 files from ID3v1 to ID3v2" in result.stdout
    assert "Stripped ID3v1 from 1 files" in result.stdout

    # ID3v1 should be gone
    assert not has_id3v1_tag(mp3_no_id3v2)

    # ID3v2 should now exist with migrated data
    id3 = ID3(str(mp3_no_id3v2))
    assert "TIT2" in id3
    assert "Test Title" in str(id3["TIT2"])
    assert "TPE1" in id3
    assert "Test Artist" in str(id3["TPE1"])
    assert "TALB" in id3
    assert "Test Album" in str(id3["TALB"])


def test_strip_v1_force_strips_without_v2(runner, mp3_no_id3v2):
    """Test that --force strips ID3v1 even without ID3v2 (data loss)."""
    # Add ID3v1 tag only
    add_id3v1_tag(mp3_no_id3v2)

    result = runner.invoke(app, ["tags", "strip-v1", str(mp3_no_id3v2), "--apply", "--force"])

    assert result.exit_code == 0
    assert "Stripped ID3v1 from 1 files" in result.stdout

    # ID3v1 should be gone
    assert not has_id3v1_tag(mp3_no_id3v2)

    # No ID3v2 tags should exist (data lost)
    from mutagen.id3 import ID3NoHeaderError

    with pytest.raises(ID3NoHeaderError):
        ID3(str(mp3_no_id3v2))


def test_strip_v1_migrate_and_force_error(runner, mp3_no_id3v2):
    """Test that using both --migrate and --force raises an error."""
    add_id3v1_tag(mp3_no_id3v2)

    result = runner.invoke(app, ["tags", "strip-v1", str(mp3_no_id3v2), "--migrate", "--force"])

    assert result.exit_code == 1
    assert "Cannot use both --migrate and --force" in result.stdout


def test_strip_v1_dry_run_shows_skip_warning(runner, mp3_no_id3v2):
    """Test that dry run shows which files would be skipped."""
    # Add ID3v1 tag only
    add_id3v1_tag(mp3_no_id3v2)

    result = runner.invoke(app, ["tags", "strip-v1", str(mp3_no_id3v2)])

    assert result.exit_code == 0
    assert "would be skipped (only ID3v1)" in result.stdout
    assert "Use --migrate to copy ID3v1→ID3v2 first" in result.stdout
    # ID3v1 should still be there (dry run)
    assert has_id3v1_tag(mp3_no_id3v2)


def test_strip_v1_migrate_dry_run(runner, mp3_no_id3v2):
    """Test that --migrate dry run shows what would happen."""
    # Add ID3v1 tag only
    add_id3v1_tag(mp3_no_id3v2)

    result = runner.invoke(app, ["tags", "strip-v1", str(mp3_no_id3v2), "--migrate"])

    assert result.exit_code == 0
    assert "Would migrate & strip" in result.stdout
    # ID3v1 should still be there (dry run)
    assert has_id3v1_tag(mp3_no_id3v2)


def test_strip_v1_no_v1_tags(runner, mp3_no_id3v2):
    """Test handling of files without ID3v1 tags."""
    # Don't add any ID3v1 tag

    result = runner.invoke(app, ["tags", "strip-v1", str(mp3_no_id3v2), "--apply"])

    assert result.exit_code == 0
    assert "Stripped ID3v1 from 0 files" in result.stdout
