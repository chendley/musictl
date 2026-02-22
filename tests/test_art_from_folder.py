"""Integration tests for art from-folder command."""

from pathlib import Path

import pytest
from mutagen.id3 import ID3
from mutagen.flac import FLAC
from typer.testing import CliRunner

from musictl.cli import app
from musictl.core.artwork import find_cover_image
from tests.conftest import create_test_mp3, create_test_flac, create_test_jpeg, create_test_png

runner = CliRunner()


@pytest.fixture
def album_with_cover(tmp_path):
    """Album directory with audio files and a cover.jpg."""
    album = tmp_path / "Artist - Album"
    album.mkdir()
    for i in range(3):
        create_test_mp3(album / f"track_{i}.mp3")
    (album / "cover.jpg").write_bytes(create_test_jpeg())
    return album


@pytest.fixture
def album_with_front(tmp_path):
    """Album directory with front.jpg (lower priority than cover)."""
    album = tmp_path / "Artist - Album2"
    album.mkdir()
    for i in range(2):
        create_test_mp3(album / f"track_{i}.mp3")
    (album / "front.jpg").write_bytes(create_test_jpeg())
    return album


@pytest.fixture
def album_art_in_subfolder(tmp_path):
    """Album directory with art in an Artwork/ subdirectory."""
    album = tmp_path / "Artist - Album3"
    album.mkdir()
    artwork_dir = album / "Artwork"
    artwork_dir.mkdir()
    for i in range(2):
        create_test_mp3(album / f"track_{i}.mp3")
    (artwork_dir / "cover.png").write_bytes(create_test_png())
    return album


@pytest.fixture
def album_art_in_parent(tmp_path):
    """Disc subfolder where art is in the parent album directory."""
    album = tmp_path / "Artist - Album4"
    album.mkdir()
    disc1 = album / "CD1"
    disc1.mkdir()
    for i in range(2):
        create_test_mp3(disc1 / f"track_{i}.mp3")
    (album / "folder.jpg").write_bytes(create_test_jpeg())
    return disc1


class TestFindCoverImage:
    def test_find_cover_in_same_dir(self, album_with_cover):
        result = find_cover_image(album_with_cover)
        assert result is not None
        assert result.name == "cover.jpg"

    def test_find_front_fallback(self, album_with_front):
        result = find_cover_image(album_with_front)
        assert result is not None
        assert result.name == "front.jpg"

    def test_find_in_subfolder(self, album_art_in_subfolder):
        result = find_cover_image(album_art_in_subfolder)
        assert result is not None
        assert result.name == "cover.png"

    def test_find_in_parent(self, album_art_in_parent):
        result = find_cover_image(album_art_in_parent)
        assert result is not None
        assert result.name == "folder.jpg"

    def test_no_image(self, tmp_path):
        album = tmp_path / "empty_album"
        album.mkdir()
        create_test_mp3(album / "track.mp3")
        assert find_cover_image(album) is None

    def test_case_insensitive(self, tmp_path):
        album = tmp_path / "album"
        album.mkdir()
        create_test_mp3(album / "track.mp3")
        (album / "Cover.JPG").write_bytes(create_test_jpeg())
        result = find_cover_image(album)
        assert result is not None
        assert result.name == "Cover.JPG"

    def test_single_image_fallback(self, tmp_path):
        album = tmp_path / "album"
        album.mkdir()
        create_test_mp3(album / "track.mp3")
        (album / "random_name.jpg").write_bytes(create_test_jpeg())
        result = find_cover_image(album)
        assert result is not None
        assert result.name == "random_name.jpg"

    def test_multiple_unknown_images_skipped(self, tmp_path):
        album = tmp_path / "album"
        album.mkdir()
        create_test_mp3(album / "track.mp3")
        (album / "scan1.jpg").write_bytes(create_test_jpeg())
        (album / "scan2.jpg").write_bytes(create_test_jpeg())
        # No known name, multiple images -> ambiguous, returns None
        assert find_cover_image(album) is None


class TestFromFolderCommand:
    def test_dry_run(self, album_with_cover):
        result = runner.invoke(app, ["art", "from-folder", str(album_with_cover)])
        assert result.exit_code == 0
        assert "Would embed in 3 files" in result.output
        assert "Dry run" in result.output

        # Verify nothing changed
        id3 = ID3(str(album_with_cover / "track_0.mp3"))
        assert not id3.getall("APIC")

    def test_apply(self, album_with_cover):
        result = runner.invoke(app, [
            "art", "from-folder", str(album_with_cover), "--apply",
        ])
        assert result.exit_code == 0
        assert "Embedded in 3 files" in result.output

        id3 = ID3(str(album_with_cover / "track_0.mp3"))
        assert id3.getall("APIC")

    def test_skip_files_with_art(self, album_with_cover, sample_jpeg):
        # Pre-embed art in one file
        from musictl.core.artwork import embed_artwork
        embed_artwork(album_with_cover / "track_0.mp3", sample_jpeg, "image/jpeg")

        result = runner.invoke(app, [
            "art", "from-folder", str(album_with_cover), "--apply",
        ])
        assert result.exit_code == 0
        assert "Embedded in 2 files" in result.output

    def test_overwrite(self, album_with_cover, sample_jpeg):
        from musictl.core.artwork import embed_artwork
        embed_artwork(album_with_cover / "track_0.mp3", sample_jpeg, "image/jpeg")

        result = runner.invoke(app, [
            "art", "from-folder", str(album_with_cover), "--overwrite", "--apply",
        ])
        assert result.exit_code == 0
        assert "Embedded in 3 files" in result.output

    def test_no_image_found(self, tmp_path):
        album = tmp_path / "no_art"
        album.mkdir()
        for i in range(2):
            create_test_mp3(album / f"track_{i}.mp3")

        result = runner.invoke(app, ["art", "from-folder", str(album)])
        assert result.exit_code == 0
        assert "no cover image" in result.output.lower()

    def test_subfolder_art(self, album_art_in_subfolder):
        result = runner.invoke(app, [
            "art", "from-folder", str(album_art_in_subfolder), "--apply",
        ])
        assert result.exit_code == 0
        assert "Embedded in 2 files" in result.output

    def test_multiple_albums(self, tmp_path):
        # Create two albums, one with cover, one without
        album1 = tmp_path / "Album1"
        album1.mkdir()
        create_test_mp3(album1 / "track.mp3")
        (album1 / "cover.jpg").write_bytes(create_test_jpeg())

        album2 = tmp_path / "Album2"
        album2.mkdir()
        create_test_mp3(album2 / "track.mp3")

        result = runner.invoke(app, ["art", "from-folder", str(tmp_path), "--apply"])
        assert result.exit_code == 0
        assert "Embedded artwork in 1 files" in result.output
        assert "1 directories have no cover image" in result.output

    def test_nonexistent_path(self):
        result = runner.invoke(app, ["art", "from-folder", "/nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
