"""Pytest fixtures and test utilities."""

import subprocess
from pathlib import Path

import pytest
from mutagen.id3 import ID3, TIT2, TPE1, TALB
from mutagen.flac import FLAC
from mutagen.mp3 import MP3


def create_test_mp3(path: Path, duration: float = 0.1, sample_rate: int = 44100):
    """Create a minimal valid MP3 file using ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"anullsrc=r={sample_rate}:cl=mono",
            "-t", str(duration),
            "-q:a", "9",
            "-y",
            str(path),
        ],
        capture_output=True,
        check=True,
    )


def create_test_flac(path: Path, duration: float = 0.1, sample_rate: int = 44100, bit_depth: int = 16):
    """Create a minimal valid FLAC file using ffmpeg."""
    # Map bit depth to ffmpeg sample format for FLAC
    sample_fmt_map = {16: "s16", 24: "s32", 32: "s32"}
    sample_fmt = sample_fmt_map.get(bit_depth, "s16")

    subprocess.run(
        [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"anullsrc=r={sample_rate}:cl=mono",
            "-t", str(duration),
            "-sample_fmt", sample_fmt,
            "-y",
            str(path),
        ],
        capture_output=True,
        check=True,
    )


@pytest.fixture
def temp_music_dir(tmp_path):
    """Create a temporary directory for test music files."""
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    return music_dir


@pytest.fixture
def sample_mp3(temp_music_dir):
    """Create a minimal valid MP3 file with ID3v2 tags."""
    mp3_path = temp_music_dir / "sample.mp3"
    create_test_mp3(mp3_path)

    # Add ID3v2 tags
    audio = MP3(str(mp3_path))
    audio["TIT2"] = TIT2(encoding=3, text="Test Song")
    audio["TPE1"] = TPE1(encoding=3, text="Test Artist")
    audio["TALB"] = TALB(encoding=3, text="Test Album")
    audio.save()

    return mp3_path


@pytest.fixture
def sample_mp3_with_v1(temp_music_dir):
    """Create an MP3 file with both ID3v1 and ID3v2 tags."""
    mp3_path = temp_music_dir / "with_v1.mp3"
    create_test_mp3(mp3_path)

    # Add ID3v2 tags
    audio = MP3(str(mp3_path))
    audio["TIT2"] = TIT2(encoding=3, text="Test Song")
    audio["TPE1"] = TPE1(encoding=3, text="Test Artist")
    audio.save()

    # Add ID3v1 tag manually
    id3v1_tag = bytearray(128)
    id3v1_tag[0:3] = b"TAG"
    id3v1_tag[3:33] = b"Test Song".ljust(30, b"\x00")
    id3v1_tag[33:63] = b"Test Artist".ljust(30, b"\x00")
    id3v1_tag[63:93] = b"Test Album".ljust(30, b"\x00")

    with open(mp3_path, "ab") as f:
        f.write(bytes(id3v1_tag))

    return mp3_path


@pytest.fixture
def sample_mp3_bad_encoding(temp_music_dir):
    """Create an MP3 with mis-encoded tags (CP1251 stored as latin-1)."""
    mp3_path = temp_music_dir / "bad_encoding.mp3"
    create_test_mp3(mp3_path)

    # Simulate mis-encoded Cyrillic text
    # "Тест" in CP1251, but stored incorrectly as latin-1
    cyrillic_text = "Тест".encode("cp1251").decode("latin-1")

    audio = MP3(str(mp3_path))
    audio["TIT2"] = TIT2(encoding=0, text=cyrillic_text)  # encoding=0 is latin-1
    audio["TPE1"] = TPE1(encoding=3, text="Test Artist")
    audio.save()

    return mp3_path


@pytest.fixture
def sample_flac(temp_music_dir):
    """Create a minimal valid FLAC file with tags."""
    flac_path = temp_music_dir / "sample.flac"
    create_test_flac(flac_path)

    # Add Vorbis comments
    audio = FLAC(str(flac_path))
    audio["TITLE"] = "Test Song"
    audio["ARTIST"] = "Test Artist"
    audio["ALBUM"] = "Test Album"
    audio.save()

    return flac_path


@pytest.fixture
def sample_flac_hires(temp_music_dir):
    """Create a FLAC file with hi-res metadata (96kHz/24bit)."""
    flac_path = temp_music_dir / "hires.flac"
    create_test_flac(flac_path, sample_rate=96000, bit_depth=24)

    audio = FLAC(str(flac_path))
    audio["TITLE"] = "Hi-Res Song"
    audio.save()

    return flac_path


@pytest.fixture
def sample_library(temp_music_dir):
    """Create a small library with multiple files in subdirectories."""
    # Create directory structure
    rock = temp_music_dir / "Rock"
    jazz = temp_music_dir / "Jazz"
    rock.mkdir()
    jazz.mkdir()

    files = []

    # Rock MP3s
    for i in range(3):
        mp3_path = rock / f"song_{i}.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text=f"Rock Song {i}")
        audio["TPE1"] = TPE1(encoding=3, text="Rock Band")
        audio.save()
        files.append(mp3_path)

    # Jazz FLACs
    for i in range(2):
        flac_path = jazz / f"track_{i}.flac"
        create_test_flac(flac_path)
        audio = FLAC(str(flac_path))
        audio["TITLE"] = f"Jazz Track {i}"
        audio["ARTIST"] = "Jazz Artist"
        audio.save()
        files.append(flac_path)

    return temp_music_dir, files


@pytest.fixture
def sample_various_artists(temp_music_dir):
    """Create files with various "Various Artists" tag variants."""
    variants = ["v/a", "V.A.", "va", "Various", "Various Artists", "v / a"]
    files = []

    for i, variant in enumerate(variants):
        mp3_path = temp_music_dir / f"compilation_{i}.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TIT2"] = TIT2(encoding=3, text=f"Song {i}")
        audio["TPE1"] = TPE1(encoding=3, text=variant)
        audio.save()
        files.append(mp3_path)

    return files


@pytest.fixture
def sample_messy_tags(temp_music_dir):
    """Create a file with messy tags (whitespace, empty tags)."""
    mp3_path = temp_music_dir / "messy.mp3"
    create_test_mp3(mp3_path)

    audio = MP3(str(mp3_path))
    audio["TIT2"] = TIT2(encoding=3, text="  Song  With   Spaces  ")
    audio["TPE1"] = TPE1(encoding=3, text=" Artist ")
    audio["TALB"] = TALB(encoding=3, text="")  # Empty tag
    audio.save()

    return mp3_path
