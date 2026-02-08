"""Tests for genre normalization in normalize command."""

import pytest
from mutagen.flac import FLAC
from mutagen.id3 import TCON
from mutagen.mp3 import MP3
from typer.testing import CliRunner

from musictl.cli import app
from tests.conftest import create_test_mp3, create_test_flac


runner = CliRunner()


@pytest.fixture
def mp3_with_genre_variants(temp_music_dir):
    """Create MP3 files with various genre spellings."""
    files = []

    # Lowercase genre
    mp3_1 = temp_music_dir / "lowercase.mp3"
    create_test_mp3(mp3_1)
    audio = MP3(str(mp3_1))
    audio["TCON"] = TCON(encoding=3, text="rock")
    audio.save()
    files.append(mp3_1)

    # Uppercase genre
    mp3_2 = temp_music_dir / "uppercase.mp3"
    create_test_mp3(mp3_2)
    audio = MP3(str(mp3_2))
    audio["TCON"] = TCON(encoding=3, text="JAZZ")
    audio.save()
    files.append(mp3_2)

    # Hip-Hop variant
    mp3_3 = temp_music_dir / "hiphop.mp3"
    create_test_mp3(mp3_3)
    audio = MP3(str(mp3_3))
    audio["TCON"] = TCON(encoding=3, text="hip hop")
    audio.save()
    files.append(mp3_3)

    # R&B variant
    mp3_4 = temp_music_dir / "rnb.mp3"
    create_test_mp3(mp3_4)
    audio = MP3(str(mp3_4))
    audio["TCON"] = TCON(encoding=3, text="rnb")
    audio.save()
    files.append(mp3_4)

    return files


class TestGenreNormalization:
    """Test genre normalization functionality."""

    def test_normalize_lowercase_genre(self, temp_music_dir):
        """Test normalizing lowercase genre to titlecase."""
        mp3_path = temp_music_dir / "test.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TCON"] = TCON(encoding=3, text="rock")
        audio.save()

        result = runner.invoke(app, [
            "tags", "normalize",
            str(mp3_path),
            "--apply"
        ])

        assert result.exit_code == 0

        # Verify genre was normalized
        audio = MP3(str(mp3_path))
        assert str(audio["TCON"]) == "Rock"

    def test_normalize_uppercase_genre(self, temp_music_dir):
        """Test normalizing uppercase genre to titlecase."""
        mp3_path = temp_music_dir / "test.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TCON"] = TCON(encoding=3, text="JAZZ")
        audio.save()

        result = runner.invoke(app, [
            "tags", "normalize",
            str(mp3_path),
            "--apply"
        ])

        assert result.exit_code == 0

        # Verify genre was normalized
        audio = MP3(str(mp3_path))
        assert str(audio["TCON"]) == "Jazz"

    def test_normalize_hiphop_variants(self, temp_music_dir):
        """Test normalizing Hip-Hop variants."""
        variants = ["hip hop", "hiphop", "Hip Hop", "HIPHOP", "rap"]

        for i, variant in enumerate(variants):
            mp3_path = temp_music_dir / f"test_{i}.mp3"
            create_test_mp3(mp3_path)
            audio = MP3(str(mp3_path))
            audio["TCON"] = TCON(encoding=3, text=variant)
            audio.save()

        result = runner.invoke(app, [
            "tags", "normalize",
            str(temp_music_dir),
            "--apply"
        ])

        assert result.exit_code == 0

        # Verify all variants were normalized to "Hip-Hop"
        for i in range(len(variants)):
            mp3_path = temp_music_dir / f"test_{i}.mp3"
            audio = MP3(str(mp3_path))
            assert str(audio["TCON"]) == "Hip-Hop"

    def test_normalize_rnb_variants(self, temp_music_dir):
        """Test normalizing R&B variants."""
        variants = ["rnb", "r&b", "r & b", "RNB", "rhythm and blues"]

        for i, variant in enumerate(variants):
            mp3_path = temp_music_dir / f"test_{i}.mp3"
            create_test_mp3(mp3_path)
            audio = MP3(str(mp3_path))
            audio["TCON"] = TCON(encoding=3, text=variant)
            audio.save()

        result = runner.invoke(app, [
            "tags", "normalize",
            str(temp_music_dir),
            "--apply"
        ])

        assert result.exit_code == 0

        # Verify all variants were normalized to "R&B"
        for i in range(len(variants)):
            mp3_path = temp_music_dir / f"test_{i}.mp3"
            audio = MP3(str(mp3_path))
            assert str(audio["TCON"]) == "R&B"

    def test_normalize_alternative_variants(self, temp_music_dir):
        """Test normalizing Alternative variants."""
        mp3_path = temp_music_dir / "test.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TCON"] = TCON(encoding=3, text="alt")
        audio.save()

        result = runner.invoke(app, [
            "tags", "normalize",
            str(mp3_path),
            "--apply"
        ])

        assert result.exit_code == 0

        # Verify genre was normalized
        audio = MP3(str(mp3_path))
        assert str(audio["TCON"]) == "Alternative"

    def test_normalize_rock_variants(self, temp_music_dir):
        """Test normalizing Rock variants."""
        variants = {
            "rock": "Rock",
            "rock and roll": "Rock & Roll",
            "rock & roll": "Rock & Roll",
            "rock'n'roll": "Rock & Roll",
        }

        for i, (variant, expected) in enumerate(variants.items()):
            mp3_path = temp_music_dir / f"test_{i}.mp3"
            create_test_mp3(mp3_path)
            audio = MP3(str(mp3_path))
            audio["TCON"] = TCON(encoding=3, text=variant)
            audio.save()

        result = runner.invoke(app, [
            "tags", "normalize",
            str(temp_music_dir),
            "--apply"
        ])

        assert result.exit_code == 0

        # Verify variants were normalized correctly
        for i, expected in enumerate(variants.values()):
            mp3_path = temp_music_dir / f"test_{i}.mp3"
            audio = MP3(str(mp3_path))
            assert str(audio["TCON"]) == expected

    def test_normalize_unmapped_genre_titlecase(self, temp_music_dir):
        """Test that unmapped genres get titlecased."""
        mp3_path = temp_music_dir / "test.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TCON"] = TCON(encoding=3, text="some weird genre")
        audio.save()

        result = runner.invoke(app, [
            "tags", "normalize",
            str(mp3_path),
            "--apply"
        ])

        assert result.exit_code == 0

        # Verify genre was titlecased
        audio = MP3(str(mp3_path))
        assert str(audio["TCON"]) == "Some Weird Genre"

    def test_normalize_genre_dry_run(self, temp_music_dir):
        """Test genre normalization in dry-run mode."""
        mp3_path = temp_music_dir / "test.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TCON"] = TCON(encoding=3, text="rock")
        audio.save()

        result = runner.invoke(app, [
            "tags", "normalize",
            str(mp3_path)
        ])

        assert result.exit_code == 0
        assert "Dry run" in result.stdout
        assert "rock" in result.stdout
        assert "Rock" in result.stdout

        # Verify genre was NOT modified
        audio = MP3(str(mp3_path))
        assert str(audio["TCON"]) == "rock"

    def test_normalize_genre_flac(self, temp_music_dir):
        """Test genre normalization for FLAC files."""
        flac_path = temp_music_dir / "test.flac"
        create_test_flac(flac_path)
        audio = FLAC(str(flac_path))
        audio["GENRE"] = "electronic"
        audio.save()

        result = runner.invoke(app, [
            "tags", "normalize",
            str(flac_path),
            "--apply"
        ])

        assert result.exit_code == 0

        # Verify genre was normalized
        audio = FLAC(str(flac_path))
        assert audio["GENRE"][0] == "Electronic"

    def test_normalize_multiple_genres(self, temp_music_dir):
        """Test normalizing multiple genre tags."""
        mp3_path = temp_music_dir / "test.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TCON"] = TCON(encoding=3, text=["rock", "blues", "jazz"])
        audio.save()

        result = runner.invoke(app, [
            "tags", "normalize",
            str(mp3_path),
            "--apply"
        ])

        assert result.exit_code == 0

        # Verify all genres were normalized
        audio = MP3(str(mp3_path))
        genres = [str(g) for g in audio["TCON"].text]
        assert "Rock" in genres
        assert "Blues" in genres
        assert "Jazz" in genres

    def test_normalize_genre_with_whitespace(self, temp_music_dir):
        """Test normalizing genre with extra whitespace."""
        mp3_path = temp_music_dir / "test.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TCON"] = TCON(encoding=3, text="  rock  ")
        audio.save()

        result = runner.invoke(app, [
            "tags", "normalize",
            str(mp3_path),
            "--apply"
        ])

        assert result.exit_code == 0

        # Verify genre was normalized and whitespace removed
        audio = MP3(str(mp3_path))
        assert str(audio["TCON"]) == "Rock"

    def test_normalize_preserves_correct_genre(self, temp_music_dir):
        """Test that correctly formatted genres are preserved."""
        mp3_path = temp_music_dir / "test.mp3"
        create_test_mp3(mp3_path)
        audio = MP3(str(mp3_path))
        audio["TCON"] = TCON(encoding=3, text="Rock")
        audio.save()

        result = runner.invoke(app, [
            "tags", "normalize",
            str(mp3_path),
            "--apply"
        ])

        assert result.exit_code == 0

        # Verify genre unchanged
        audio = MP3(str(mp3_path))
        assert str(audio["TCON"]) == "Rock"

    def test_normalize_batch_genre_files(self, mp3_with_genre_variants):
        """Test normalizing multiple files with genre variants."""
        music_dir = mp3_with_genre_variants[0].parent

        result = runner.invoke(app, [
            "tags", "normalize",
            str(music_dir),
            "--apply"
        ])

        assert result.exit_code == 0
        assert "4 files" in result.stdout or "Normalized tags in 4 files" in result.stdout

        # Verify all files were normalized
        for file_path in mp3_with_genre_variants:
            audio = MP3(str(file_path))
            genre = str(audio["TCON"])
            # Should be titlecased or mapped variant
            assert genre[0].isupper()  # First letter uppercase
