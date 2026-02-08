"""Filename pattern parsing and metadata extraction."""

import re
from pathlib import Path
from typing import Dict, List, Optional


class FilenamePattern:
    """Parse filenames using pattern templates to extract metadata."""

    # Supported field names
    FIELDS = {
        "artist": "Artist name",
        "album": "Album name",
        "title": "Song title",
        "track": "Track number",
        "year": "Year",
        "albumartist": "Album artist",
    }

    def __init__(self, pattern: str):
        """Initialize with a pattern template.

        Args:
            pattern: Template with {field} placeholders, e.g. "{artist} - {title}"

        Raises:
            ValueError: If pattern contains unknown fields
        """
        self.pattern = pattern
        self.fields_in_pattern: List[str] = []
        self.regex = self._compile_pattern(pattern)

    def _compile_pattern(self, pattern: str) -> re.Pattern:
        """Convert pattern template to regex.

        Args:
            pattern: Template string like "{artist} - {title}"

        Returns:
            Compiled regex pattern

        Raises:
            ValueError: If pattern contains unknown fields
        """
        # Find all {field} placeholders
        field_regex = re.compile(r'\{(\w+)\}')
        fields = field_regex.findall(pattern)

        # Validate all fields are known
        for field in fields:
            if field not in self.FIELDS:
                valid_fields = ", ".join(self.FIELDS.keys())
                raise ValueError(
                    f"Unknown field '{field}' in pattern. "
                    f"Valid fields: {valid_fields}"
                )

        self.fields_in_pattern = fields

        # Validate at least one field is present
        if not fields:
            raise ValueError("Pattern must contain at least one field placeholder (e.g., {artist}, {title})")

        # Convert pattern to regex
        # Escape special regex characters in literal parts
        regex_pattern = re.escape(pattern)

        # Replace escaped placeholders with capture groups
        # Track numbers: match digits with optional leading zeros
        regex_pattern = regex_pattern.replace(r'\{track\}', r'(?P<track>\d+)')
        # Year: match 4 digits
        regex_pattern = regex_pattern.replace(r'\{year\}', r'(?P<year>\d{4})')
        # Text fields: match non-greedy anything except common separators
        for field in ['artist', 'album', 'title', 'albumartist']:
            # Non-greedy match, stop at separators or end
            regex_pattern = regex_pattern.replace(
                f'\\{{{field}\\}}',
                f'(?P<{field}>.+?)'
            )

        # Add pattern to stop at file extension
        regex_pattern = regex_pattern + r'(?:\.\w+)?$'

        return re.compile(regex_pattern)

    def parse(self, filename: str) -> Optional[Dict[str, str]]:
        """Extract metadata from filename using pattern.

        Args:
            filename: Filename to parse (with or without extension)

        Returns:
            Dict of field -> value if pattern matches, None otherwise
        """
        # Remove path, keep only filename
        filename = Path(filename).name

        # Try to match pattern
        match = self.regex.match(filename)
        if not match:
            return None

        # Extract matched fields
        result = {}
        for field in self.fields_in_pattern:
            value = match.group(field)
            if value:
                # Clean up the value
                value = value.strip()

                # Normalize track numbers (remove leading zeros)
                if field == 'track':
                    try:
                        value = str(int(value))
                    except ValueError:
                        pass

                result[field] = value

        return result if result else None

    def __repr__(self) -> str:
        return f"FilenamePattern(pattern='{self.pattern}')"


def parse_filename(filename: str, pattern: str) -> Optional[Dict[str, str]]:
    """Convenience function to parse a filename with a pattern.

    Args:
        filename: Filename to parse
        pattern: Pattern template

    Returns:
        Dict of extracted fields, or None if no match
    """
    parser = FilenamePattern(pattern)
    return parser.parse(filename)
