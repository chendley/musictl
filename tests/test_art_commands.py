"""Integration tests for album art commands."""

from pathlib import Path

import pytest
from mutagen.id3 import ID3
from mutagen.flac import FLAC
from typer.testing import CliRunner

from musictl.cli import app
from tests.conftest import create_test_mp3, create_test_flac

runner = CliRunner()


class TestArtShow:
    def test_show_mp3_with_art(self, sample_mp3_with_art):
        result = runner.invoke(app, ["art", "show", str(sample_mp3_with_art)])
        assert result.exit_code == 0
        assert "Front Cover" in result.output
        assert "image/jpeg" in result.output
        assert "1 files with artwork" in result.output

    def test_show_flac_with_art(self, sample_flac_with_art):
        result = runner.invoke(app, ["art", "show", str(sample_flac_with_art)])
        assert result.exit_code == 0
        assert "Front Cover" in result.output
        assert "image/png" in result.output
        assert "2x2" in result.output

    def test_show_no_art(self, sample_mp3):
        result = runner.invoke(app, ["art", "show", str(sample_mp3)])
        assert result.exit_code == 0
        assert "No artwork" in result.output
        assert "0 files with artwork" in result.output

    def test_show_directory(self, sample_mp3_with_art, sample_mp3):
        music_dir = sample_mp3_with_art.parent
        result = runner.invoke(app, ["art", "show", str(music_dir)])
        assert result.exit_code == 0
        assert "1 files with artwork" in result.output
        assert "1 without" in result.output

    def test_show_nonexistent_path(self):
        result = runner.invoke(app, ["art", "show", "/nonexistent/path"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestArtEmbed:
    def test_embed_dry_run(self, sample_mp3, sample_cover_jpg):
        result = runner.invoke(app, [
            "art", "embed", str(sample_mp3),
            "--image", str(sample_cover_jpg),
        ])
        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert "Would embed" in result.output

        # Verify no art was actually embedded
        id3 = ID3(str(sample_mp3))
        assert not id3.getall("APIC")

    def test_embed_mp3_apply(self, sample_mp3, sample_cover_jpg):
        result = runner.invoke(app, [
            "art", "embed", str(sample_mp3),
            "--image", str(sample_cover_jpg), "--apply",
        ])
        assert result.exit_code == 0
        assert "Embedded artwork in 1 files" in result.output

        id3 = ID3(str(sample_mp3))
        apics = id3.getall("APIC")
        assert len(apics) == 1
        assert apics[0].mime == "image/jpeg"

    def test_embed_flac_apply(self, sample_flac, sample_cover_png):
        result = runner.invoke(app, [
            "art", "embed", str(sample_flac),
            "--image", str(sample_cover_png), "--apply",
        ])
        assert result.exit_code == 0
        assert "Embedded artwork in 1 files" in result.output

        audio = FLAC(str(sample_flac))
        assert len(audio.pictures) == 1
        assert audio.pictures[0].mime == "image/png"

    def test_embed_skip_existing(self, sample_mp3_with_art, sample_cover_jpg):
        result = runner.invoke(app, [
            "art", "embed", str(sample_mp3_with_art),
            "--image", str(sample_cover_jpg), "--apply",
        ])
        assert result.exit_code == 0
        assert "Skipped 1 files" in result.output

    def test_embed_overwrite_existing(self, sample_mp3_with_art, sample_cover_jpg):
        result = runner.invoke(app, [
            "art", "embed", str(sample_mp3_with_art),
            "--image", str(sample_cover_jpg), "--overwrite", "--apply",
        ])
        assert result.exit_code == 0
        assert "Embedded artwork in 1 files" in result.output

    def test_embed_directory(self, sample_library, sample_cover_jpg):
        music_dir, files = sample_library
        result = runner.invoke(app, [
            "art", "embed", str(music_dir),
            "--image", str(sample_cover_jpg), "--apply",
        ])
        assert result.exit_code == 0
        assert "Embedded artwork in 5 files" in result.output

    def test_embed_missing_image(self, sample_mp3):
        result = runner.invoke(app, [
            "art", "embed", str(sample_mp3),
            "--image", "/nonexistent/cover.jpg",
        ])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_embed_nonexistent_path(self, sample_cover_jpg):
        result = runner.invoke(app, [
            "art", "embed", "/nonexistent/path",
            "--image", str(sample_cover_jpg),
        ])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestArtExtract:
    def test_extract_dry_run(self, sample_mp3_with_art):
        result = runner.invoke(app, [
            "art", "extract", str(sample_mp3_with_art),
        ])
        assert result.exit_code == 0
        assert "Would extract" in result.output
        assert "cover.jpg" in result.output

    def test_extract_apply(self, sample_mp3_with_art, tmp_path):
        dest = tmp_path / "extracted"
        dest.mkdir()
        result = runner.invoke(app, [
            "art", "extract", str(sample_mp3_with_art),
            "--dest", str(dest), "--apply",
        ])
        assert result.exit_code == 0
        assert "Extracted artwork from 1 directories" in result.output
        assert (dest / "cover.jpg").exists()

    def test_extract_flac(self, sample_flac_with_art, tmp_path):
        dest = tmp_path / "extracted"
        dest.mkdir()
        result = runner.invoke(app, [
            "art", "extract", str(sample_flac_with_art),
            "--dest", str(dest), "--apply",
        ])
        assert result.exit_code == 0
        assert (dest / "cover.png").exists()

    def test_extract_no_art(self, sample_mp3, tmp_path):
        dest = tmp_path / "extracted"
        dest.mkdir()
        result = runner.invoke(app, [
            "art", "extract", str(sample_mp3),
            "--dest", str(dest), "--apply",
        ])
        assert result.exit_code == 0
        assert "Extracted artwork from 0 directories" in result.output
        assert not list(dest.iterdir())

    def test_extract_skip_existing(self, sample_mp3_with_art, tmp_path):
        dest = tmp_path / "extracted"
        dest.mkdir()
        # Create existing file
        (dest / "cover.jpg").write_bytes(b"existing")
        result = runner.invoke(app, [
            "art", "extract", str(sample_mp3_with_art),
            "--dest", str(dest), "--apply",
        ])
        assert result.exit_code == 0
        # Should have skipped
        assert (dest / "cover.jpg").read_bytes() == b"existing"

    def test_extract_overwrite(self, sample_mp3_with_art, tmp_path):
        dest = tmp_path / "extracted"
        dest.mkdir()
        (dest / "cover.jpg").write_bytes(b"existing")
        result = runner.invoke(app, [
            "art", "extract", str(sample_mp3_with_art),
            "--dest", str(dest), "--overwrite", "--apply",
        ])
        assert result.exit_code == 0
        # Should have been overwritten
        assert (dest / "cover.jpg").read_bytes() != b"existing"

    def test_extract_default_dest(self, sample_mp3_with_art):
        result = runner.invoke(app, [
            "art", "extract", str(sample_mp3_with_art), "--apply",
        ])
        assert result.exit_code == 0
        cover_path = sample_mp3_with_art.parent / "cover.jpg"
        assert cover_path.exists()


class TestArtRemove:
    def test_remove_dry_run(self, sample_mp3_with_art):
        result = runner.invoke(app, [
            "art", "remove", str(sample_mp3_with_art),
        ])
        assert result.exit_code == 0
        assert "Would remove" in result.output

        # Verify art still exists
        id3 = ID3(str(sample_mp3_with_art))
        assert id3.getall("APIC")

    def test_remove_apply(self, sample_mp3_with_art):
        result = runner.invoke(app, [
            "art", "remove", str(sample_mp3_with_art), "--apply",
        ])
        assert result.exit_code == 0
        assert "Removed artwork from 1 files" in result.output

        id3 = ID3(str(sample_mp3_with_art))
        assert not id3.getall("APIC")

    def test_remove_no_art(self, sample_mp3):
        result = runner.invoke(app, [
            "art", "remove", str(sample_mp3), "--apply",
        ])
        assert result.exit_code == 0
        assert "Removed artwork from 0 files" in result.output

    def test_remove_flac(self, sample_flac_with_art):
        result = runner.invoke(app, [
            "art", "remove", str(sample_flac_with_art), "--apply",
        ])
        assert result.exit_code == 0
        assert "Removed artwork from 1 files" in result.output

        audio = FLAC(str(sample_flac_with_art))
        assert len(audio.pictures) == 0

    def test_remove_directory(self, sample_mp3_with_art, sample_mp3):
        music_dir = sample_mp3_with_art.parent
        result = runner.invoke(app, [
            "art", "remove", str(music_dir), "--apply",
        ])
        assert result.exit_code == 0
        assert "Removed artwork from 1 files" in result.output
        assert "1 files had no artwork" in result.output
