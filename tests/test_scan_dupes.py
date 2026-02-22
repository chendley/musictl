"""Integration tests for scan dupes command."""

import csv
import json
import shutil
from pathlib import Path

import pytest
from mutagen.id3 import TIT2, TPE1
from mutagen.mp3 import MP3
from typer.testing import CliRunner

from musictl.cli import app
from tests.conftest import create_test_mp3

runner = CliRunner()


@pytest.fixture
def no_dupes(tmp_path):
    """Directory with unique files (no duplicates)."""
    for i in range(3):
        mp3_path = tmp_path / f"unique_{i}.mp3"
        create_test_mp3(mp3_path, duration=0.1 + i * 0.05)
    return tmp_path


@pytest.fixture
def exact_dupes(tmp_path):
    """Directory with exact duplicate files."""
    original = tmp_path / "original.mp3"
    create_test_mp3(original)
    # Exact copy
    shutil.copy2(original, tmp_path / "copy1.mp3")
    shutil.copy2(original, tmp_path / "copy2.mp3")
    # One unique file
    create_test_mp3(tmp_path / "unique.mp3", duration=0.2)
    return tmp_path


@pytest.fixture
def multiple_groups(tmp_path):
    """Directory with multiple groups of duplicates."""
    orig_a = tmp_path / "group_a.mp3"
    create_test_mp3(orig_a, duration=0.1)
    shutil.copy2(orig_a, tmp_path / "group_a_copy.mp3")

    orig_b = tmp_path / "group_b.mp3"
    create_test_mp3(orig_b, duration=0.2)
    shutil.copy2(orig_b, tmp_path / "group_b_copy.mp3")

    return tmp_path


@pytest.fixture
def fuzzy_dupes(tmp_path):
    """Directory with files sharing artist/title/duration (fuzzy dupes)."""
    for i, sr in enumerate([44100, 96000]):
        mp3_path = tmp_path / f"track_{sr}.mp3"
        create_test_mp3(mp3_path, sample_rate=sr)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text="Same Song")
        audio["TPE1"] = TPE1(encoding=3, text="Same Artist")
        audio.save()
    return tmp_path


class TestScanDupes:
    def test_no_duplicates(self, no_dupes):
        result = runner.invoke(app, ["scan", "dupes", str(no_dupes)])
        assert result.exit_code == 0
        assert "No duplicates found" in result.output

    def test_exact_duplicates(self, exact_dupes):
        result = runner.invoke(app, ["scan", "dupes", str(exact_dupes)])
        assert result.exit_code == 0
        assert "1 duplicate groups" in result.output
        assert "2 duplicate files" in result.output
        assert "(keep)" in result.output
        assert "(duplicate)" in result.output

    def test_multiple_groups(self, multiple_groups):
        result = runner.invoke(app, ["scan", "dupes", str(multiple_groups)])
        assert result.exit_code == 0
        assert "2 duplicate groups" in result.output

    def test_summary_mode(self, exact_dupes):
        result = runner.invoke(app, ["scan", "dupes", str(exact_dupes), "--summary"])
        assert result.exit_code == 0
        assert "1 duplicate groups" in result.output
        # Summary should NOT show individual file paths
        assert "(keep)" not in result.output

    def test_fuzzy_mode(self, fuzzy_dupes):
        result = runner.invoke(app, ["scan", "dupes", str(fuzzy_dupes), "--fuzzy"])
        assert result.exit_code == 0
        assert "1 duplicate groups" in result.output
        assert "same artist - same song" in result.output

    def test_export_csv(self, exact_dupes, tmp_path):
        export_path = tmp_path / "output" / "dupes.csv"
        export_path.parent.mkdir()
        result = runner.invoke(app, [
            "scan", "dupes", str(exact_dupes),
            "--export", str(export_path),
        ])
        assert result.exit_code == 0
        assert export_path.exists()

        with open(export_path) as f:
            reader = csv.reader(f)
            rows = list(reader)
        # Header + 3 files (1 group of 3)
        assert rows[0] == ["Group", "File", "Size", "Status"]
        assert len(rows) == 4
        assert rows[1][3] == "keep"
        assert rows[2][3] == "duplicate"

    def test_export_json(self, exact_dupes, tmp_path):
        export_path = tmp_path / "output" / "dupes.json"
        export_path.parent.mkdir()
        result = runner.invoke(app, [
            "scan", "dupes", str(exact_dupes),
            "--export", str(export_path), "--format", "json",
        ])
        assert result.exit_code == 0
        assert export_path.exists()

        with open(export_path) as f:
            data = json.load(f)
        assert data["summary"]["duplicate_groups"] == 1
        assert data["summary"]["duplicate_files"] == 2
        assert len(data["groups"]) == 1
        assert len(data["groups"][0]["files"]) == 3

    def test_empty_directory(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = runner.invoke(app, ["scan", "dupes", str(empty)])
        assert result.exit_code == 0
        assert "No audio files found" in result.output

    def test_nonexistent_path(self):
        result = runner.invoke(app, ["scan", "dupes", "/nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_single_file(self, tmp_path):
        create_test_mp3(tmp_path / "only.mp3")
        result = runner.invoke(app, ["scan", "dupes", str(tmp_path)])
        assert result.exit_code == 0
        assert "No duplicates found" in result.output

    def test_no_export_when_no_dupes(self, no_dupes, tmp_path):
        export_path = tmp_path / "output" / "dupes.csv"
        export_path.parent.mkdir()
        result = runner.invoke(app, [
            "scan", "dupes", str(no_dupes),
            "--export", str(export_path),
        ])
        assert result.exit_code == 0
        assert not export_path.exists()

    def test_wasted_space_shown(self, exact_dupes):
        result = runner.invoke(app, ["scan", "dupes", str(exact_dupes)])
        assert result.exit_code == 0
        assert "wasted" in result.output.lower()
