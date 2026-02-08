"""Tests for filename pattern parsing."""

import pytest

from musictl.core.filename_parser import FilenamePattern, parse_filename


class TestFilenamePattern:
    """Test FilenamePattern class."""

    def test_simple_artist_title(self):
        """Test basic 'Artist - Title' pattern."""
        pattern = FilenamePattern("{artist} - {title}")
        result = pattern.parse("The Beatles - Hey Jude.mp3")

        assert result is not None
        assert result["artist"] == "The Beatles"
        assert result["title"] == "Hey Jude"

    def test_track_title(self):
        """Test 'Track. Title' pattern."""
        pattern = FilenamePattern("{track}. {title}")
        result = pattern.parse("01. Yesterday.mp3")

        assert result is not None
        assert result["track"] == "1"  # Leading zero removed
        assert result["title"] == "Yesterday"

    def test_track_with_leading_zeros(self):
        """Test track number normalization."""
        pattern = FilenamePattern("{track} - {title}")

        # Single digit with zero
        result = pattern.parse("01 - Song.mp3")
        assert result["track"] == "1"

        # Double digit
        result = pattern.parse("10 - Song.mp3")
        assert result["track"] == "10"

        # Triple digit with zeros
        result = pattern.parse("001 - Song.mp3")
        assert result["track"] == "1"

    def test_track_artist_title(self):
        """Test 'Track Artist - Title' pattern."""
        pattern = FilenamePattern("{track} {artist} - {title}")
        result = pattern.parse("05 Pink Floyd - Wish You Were Here.flac")

        assert result is not None
        assert result["track"] == "5"
        assert result["artist"] == "Pink Floyd"
        assert result["title"] == "Wish You Were Here"

    def test_full_metadata_pattern(self):
        """Test pattern with all fields."""
        pattern = FilenamePattern("{artist} - {album} - {track} - {title}")
        result = pattern.parse("Led Zeppelin - IV - 04 - Stairway to Heaven.mp3")

        assert result is not None
        assert result["artist"] == "Led Zeppelin"
        assert result["album"] == "IV"
        assert result["track"] == "4"
        assert result["title"] == "Stairway to Heaven"

    def test_year_in_pattern(self):
        """Test pattern with year field."""
        pattern = FilenamePattern("{artist} - {title} ({year})")
        result = pattern.parse("David Bowie - Space Oddity (1969).mp3")

        assert result is not None
        assert result["artist"] == "David Bowie"
        assert result["title"] == "Space Oddity"
        assert result["year"] == "1969"

    def test_no_extension(self):
        """Test parsing filename without extension."""
        pattern = FilenamePattern("{artist} - {title}")
        result = pattern.parse("Queen - Bohemian Rhapsody")

        assert result is not None
        assert result["artist"] == "Queen"
        assert result["title"] == "Bohemian Rhapsody"

    def test_different_extensions(self):
        """Test various file extensions."""
        pattern = FilenamePattern("{artist} - {title}")

        for ext in [".mp3", ".flac", ".m4a", ".ogg", ".wav"]:
            result = pattern.parse(f"Artist - Title{ext}")
            assert result is not None
            assert result["artist"] == "Artist"
            assert result["title"] == "Title"

    def test_no_match(self):
        """Test filename that doesn't match pattern."""
        pattern = FilenamePattern("{artist} - {title}")
        result = pattern.parse("JustAFilename.mp3")

        assert result is None

    def test_partial_match(self):
        """Test filename that partially matches."""
        pattern = FilenamePattern("{artist} - {album} - {title}")
        # Only has artist and title, missing album
        result = pattern.parse("Artist - Title.mp3")

        assert result is None

    def test_special_characters_in_name(self):
        """Test filenames with special characters."""
        pattern = FilenamePattern("{artist} - {title}")

        # Dots and hyphens (AC/DC stored as AC-DC on Unix)
        result = pattern.parse("AC-DC - T.N.T..mp3")
        assert result is not None
        assert result["artist"] == "AC-DC"
        assert result["title"] == "T.N.T."

        # Apostrophes
        result = pattern.parse("Guns N' Roses - Sweet Child O' Mine.mp3")
        assert result is not None
        assert result["artist"] == "Guns N' Roses"
        assert result["title"] == "Sweet Child O' Mine"

        # Ampersands
        result = pattern.parse("Simon & Garfunkel - The Sound of Silence.mp3")
        assert result is not None
        assert result["artist"] == "Simon & Garfunkel"

        # Parentheses and brackets
        result = pattern.parse("Rage Against The Machine - Killing In The Name (Live).mp3")
        assert result is not None
        assert result["artist"] == "Rage Against The Machine"
        assert result["title"] == "Killing In The Name (Live)"

    def test_unicode_characters(self):
        """Test Unicode characters in filenames."""
        pattern = FilenamePattern("{artist} - {title}")
        result = pattern.parse("Björk - Jóga.mp3")

        assert result is not None
        assert result["artist"] == "Björk"
        assert result["title"] == "Jóga"

    def test_numbers_in_title(self):
        """Test titles with numbers."""
        pattern = FilenamePattern("{artist} - {title}")
        result = pattern.parse("Gorillaz - 19-2000.mp3")

        assert result is not None
        assert result["artist"] == "Gorillaz"
        assert result["title"] == "19-2000"

    def test_whitespace_handling(self):
        """Test extra whitespace is trimmed."""
        pattern = FilenamePattern("{artist} - {title}")
        result = pattern.parse("  Artist  -  Title  .mp3")

        assert result is not None
        assert result["artist"] == "Artist"
        assert result["title"] == "Title"

    def test_ambiguous_separator(self):
        """Test when separator-like text appears in field value."""
        # Pattern uses " - " as separator, but artist name also has "-"
        pattern = FilenamePattern("{artist} - {title}")
        result = pattern.parse("AC-DC - Back in Black.mp3")

        # Should match correctly - non-greedy matching stops at " - " separator
        assert result is not None
        assert result["artist"] == "AC-DC"
        assert result["title"] == "Back in Black"

        # Test with multiple hyphens in title
        result = pattern.parse("Artist - Song-Title-With-Hyphens.mp3")
        assert result is not None
        assert result["artist"] == "Artist"
        assert result["title"] == "Song-Title-With-Hyphens"

    def test_invalid_field_name(self):
        """Test pattern with unknown field raises error."""
        with pytest.raises(ValueError, match="Unknown field"):
            FilenamePattern("{artist} - {unknown}")

    def test_full_path_input(self):
        """Test that full paths are handled correctly."""
        pattern = FilenamePattern("{artist} - {title}")

        # Full path should extract just the filename
        result = pattern.parse("/home/user/Music/Artist - Song.mp3")
        assert result is not None
        assert result["artist"] == "Artist"
        assert result["title"] == "Song"

        # Nested path
        result = pattern.parse("/home/user/Music/Album/Artist - Song.flac")
        assert result is not None
        assert result["artist"] == "Artist"
        assert result["title"] == "Song"

    def test_pattern_with_no_fields(self):
        """Test pattern with no placeholders."""
        with pytest.raises(ValueError):
            # This should fail or return empty - we expect at least one field
            pattern = FilenamePattern("static text")

    def test_convenience_function(self):
        """Test parse_filename convenience function."""
        result = parse_filename(
            "Pink Floyd - Wish You Were Here.mp3",
            "{artist} - {title}"
        )

        assert result is not None
        assert result["artist"] == "Pink Floyd"
        assert result["title"] == "Wish You Were Here"

    def test_pattern_repr(self):
        """Test string representation."""
        pattern = FilenamePattern("{artist} - {title}")
        assert "artist" in repr(pattern)
        assert "title" in repr(pattern)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_filename(self):
        """Test empty filename."""
        pattern = FilenamePattern("{artist} - {title}")
        result = pattern.parse("")
        assert result is None

    def test_very_long_filename(self):
        """Test very long filename."""
        pattern = FilenamePattern("{artist} - {title}")
        long_title = "A" * 500
        result = pattern.parse(f"Artist - {long_title}.mp3")

        assert result is not None
        assert result["artist"] == "Artist"
        assert len(result["title"]) == 500

    def test_filename_with_multiple_dots(self):
        """Test filename with multiple dots."""
        pattern = FilenamePattern("{artist} - {title}")
        result = pattern.parse("Mr. Big - To Be With You.flac")

        assert result is not None
        assert result["artist"] == "Mr. Big"
        assert result["title"] == "To Be With You"

    def test_track_number_zero(self):
        """Test track number 00."""
        pattern = FilenamePattern("{track}. {title}")
        result = pattern.parse("00. Intro.mp3")

        assert result is not None
        assert result["track"] == "0"

    def test_year_with_wrong_format(self):
        """Test year field with non-4-digit value."""
        pattern = FilenamePattern("{title} ({year})")
        # Should not match if year is not 4 digits
        result = pattern.parse("Song (99).mp3")
        assert result is None

        result = pattern.parse("Song (12345).mp3")
        assert result is None

    def test_multiple_separators(self):
        """Test pattern with various separators."""
        pattern = FilenamePattern("{track} - {artist} - {title}")
        result = pattern.parse("01 - Artist - Title.mp3")

        assert result is not None
        assert result["track"] == "1"
        assert result["artist"] == "Artist"
        assert result["title"] == "Title"
