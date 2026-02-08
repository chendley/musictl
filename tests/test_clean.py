"""Tests for clean commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from musictl.cli import app


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


@pytest.fixture
def music_dir_with_temp_files(tmp_path, sample_mp3):
    """Music directory with temporary files."""
    music = tmp_path / "music"
    music.mkdir(exist_ok=True)

    # Create a valid music file
    (music / "song.mp3").write_bytes(sample_mp3.read_bytes())

    # Create temporary files
    (music / ".DS_Store").write_text("fake DS_Store")
    (music / "._song.mp3").write_text("fake resource fork")
    (music / "Thumbs.db").write_text("fake thumbs")
    (music / "desktop.ini").write_text("fake desktop.ini")
    (music / ".directory").write_text("fake directory")
    (music / "temp.tmp").write_text("fake temp")
    (music / "backup.bak").write_text("fake backup")

    # Create subdirectory with more temp files
    subdir = music / "subdir"
    subdir.mkdir()
    (subdir / ".DS_Store").write_text("fake DS_Store")
    (subdir / "file.tmp").write_text("fake temp")

    return music


def test_clean_temp_files_dry_run(runner, music_dir_with_temp_files):
    """Test clean temp-files in dry-run mode."""
    result = runner.invoke(app, ["clean", "temp-files", str(music_dir_with_temp_files)])

    assert result.exit_code == 0
    assert "Found 9 temporary files" in result.stdout
    assert "Dry run: No files deleted" in result.stdout

    # Verify files still exist
    assert (music_dir_with_temp_files / ".DS_Store").exists()
    assert (music_dir_with_temp_files / "._song.mp3").exists()
    assert (music_dir_with_temp_files / "Thumbs.db").exists()


def test_clean_temp_files_apply(runner, music_dir_with_temp_files):
    """Test clean temp-files with --apply flag."""
    result = runner.invoke(app, ["clean", "temp-files", str(music_dir_with_temp_files), "--apply"])

    assert result.exit_code == 0
    assert "Successfully deleted 9 temporary files" in result.stdout

    # Verify temp files are deleted
    assert not (music_dir_with_temp_files / ".DS_Store").exists()
    assert not (music_dir_with_temp_files / "._song.mp3").exists()
    assert not (music_dir_with_temp_files / "Thumbs.db").exists()
    assert not (music_dir_with_temp_files / "desktop.ini").exists()
    assert not (music_dir_with_temp_files / ".directory").exists()
    assert not (music_dir_with_temp_files / "temp.tmp").exists()
    assert not (music_dir_with_temp_files / "backup.bak").exists()
    assert not (music_dir_with_temp_files / "subdir" / ".DS_Store").exists()
    assert not (music_dir_with_temp_files / "subdir" / "file.tmp").exists()

    # Verify valid music file still exists
    assert (music_dir_with_temp_files / "song.mp3").exists()


def test_clean_temp_files_no_recursive(runner, music_dir_with_temp_files):
    """Test clean temp-files with --no-recursive flag."""
    result = runner.invoke(
        app, ["clean", "temp-files", str(music_dir_with_temp_files), "--no-recursive", "--apply"]
    )

    assert result.exit_code == 0
    assert "Successfully deleted 7 temporary files" in result.stdout

    # Verify top-level temp files are deleted
    assert not (music_dir_with_temp_files / ".DS_Store").exists()
    assert not (music_dir_with_temp_files / "._song.mp3").exists()

    # Verify subdirectory temp files still exist
    assert (music_dir_with_temp_files / "subdir" / ".DS_Store").exists()
    assert (music_dir_with_temp_files / "subdir" / "file.tmp").exists()


def test_clean_temp_files_no_temp_files(runner, tmp_path):
    """Test clean temp-files with no temporary files."""
    music = tmp_path / "music"
    music.mkdir()

    result = runner.invoke(app, ["clean", "temp-files", str(music)])

    assert result.exit_code == 0
    assert "No temporary files found!" in result.stdout


def test_clean_temp_files_nonexistent_path(runner, tmp_path):
    """Test clean temp-files with nonexistent path."""
    nonexistent = tmp_path / "nonexistent"

    result = runner.invoke(app, ["clean", "temp-files", str(nonexistent)])

    assert result.exit_code == 1
    assert "Path not found" in result.stdout


def test_clean_temp_files_pattern_grouping(runner, music_dir_with_temp_files):
    """Test that files are grouped by pattern in output."""
    result = runner.invoke(app, ["clean", "temp-files", str(music_dir_with_temp_files)])

    assert result.exit_code == 0
    # Check for pattern groups in output
    assert "._*:" in result.stdout
    assert ".DS_Store:" in result.stdout
    assert "Thumbs.db:" in result.stdout
    assert "desktop.ini:" in result.stdout
    assert ".directory:" in result.stdout
    assert "*.tmp:" in result.stdout
    assert "*.bak:" in result.stdout


def test_clean_temp_files_size_calculation(runner, music_dir_with_temp_files):
    """Test that file sizes are calculated correctly."""
    # Create a larger temp file to test size formatting
    large_temp = music_dir_with_temp_files / "large.tmp"
    large_temp.write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MB

    result = runner.invoke(app, ["clean", "temp-files", str(music_dir_with_temp_files)])

    assert result.exit_code == 0
    assert "MB" in result.stdout  # Should show MB for the large file
    assert "Total:" in result.stdout
    assert "files" in result.stdout
