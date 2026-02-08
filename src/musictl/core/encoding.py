"""Character encoding detection and conversion for audio tags."""

from pathlib import Path

from mutagen.id3 import ID3

# Common legacy encodings for non-Latin scripts
ENCODINGS = {
    "cp1251": "Windows-1251 (Cyrillic)",
    "cp1252": "Windows-1252 (Western European)",
    "koi8-r": "KOI8-R (Russian)",
    "koi8-u": "KOI8-U (Ukrainian)",
    "iso-8859-1": "ISO 8859-1 (Latin-1)",
    "iso-8859-5": "ISO 8859-5 (Cyrillic)",
    "shift_jis": "Shift JIS (Japanese)",
    "gb2312": "GB2312 (Chinese)",
    "euc-kr": "EUC-KR (Korean)",
}


def detect_non_utf8_tags(path: Path, encoding: str = "cp1251") -> dict[str, bytes]:
    """Check if any ID3 text frames contain mojibake (double-encoded text).

    This function looks for text where UTF-8 bytes were misinterpreted as another
    encoding and then re-saved. Common pattern with Russian/Cyrillic text:

    Example: "Аквариум" (correct UTF-8) → misread as CP1251 → "РђРєРІР°СЂРёСѓРј" (mojibake)

    Detection strategy:
    1. Skip ASCII text (can't be mojibake)
    2. Try encoding current text as `encoding`, then decoding as UTF-8
    3. Check if result contains more valid Unicode characters (e.g., Cyrillic)
    4. Only flag if reversal produces clearly better text

    Args:
        path: Path to audio file
        encoding: Encoding to test (default: cp1251 for Russian)

    Returns:
        dict of tag_key -> intermediate_bytes for tags that appear double-encoded

    SAFETY: Only returns tags that successfully round-trip AND produce better text.
    If reversal fails or produces worse text, the tag is NOT flagged.
    """
    suspect_tags: dict[str, bytes] = {}

    try:
        id3 = ID3(str(path))
    except Exception:
        return suspect_tags

    for key, frame in id3.items():
        if not key.startswith("T"):  # Only text frames
            continue

        for text in getattr(frame, "text", []):
            text_str = str(text)

            # Skip if text is all ASCII (can't be mojibake)
            if text_str.isascii():
                continue

            # Try TWO reversal patterns:
            # Pattern 1: UTF-8 mojibake (encode as encoding, decode as UTF-8)
            # Pattern 2: Wrong encoding header (encode as Latin-1, decode as encoding)

            fixed = None
            intermediate_bytes = None

            # Pattern 1: UTF-8 double-encoding mojibake
            # Example: "РђРєРІР°СЂРёСѓРј" → encode cp1251 → decode utf-8 → "Аквариум"
            try:
                test_bytes = text_str.encode(encoding)
                test_fixed = test_bytes.decode("utf-8")
                if test_fixed != text_str:
                    fixed = test_fixed
                    intermediate_bytes = test_bytes
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass

            # Pattern 2: Wrong encoding header (e.g., CP1251 bytes shown as Latin-1)
            # Example: "Òåñò" → encode latin-1 → decode cp1251 → "Тест"
            if fixed is None:
                try:
                    test_bytes = text_str.encode("latin-1")
                    test_fixed = test_bytes.decode(encoding)
                    if test_fixed != text_str:
                        fixed = test_fixed
                        intermediate_bytes = test_bytes
                except (UnicodeDecodeError, UnicodeEncodeError):
                    pass

            # If we found a reversal, check if it's actually better
            if fixed is not None and intermediate_bytes is not None:
                # Safety check: verify the "fixed" version is actually better
                # Count characters outside expected range - fewer is better
                anomalous_in_original = _count_anomalous_chars(text_str, encoding)
                anomalous_in_fixed = _count_anomalous_chars(fixed, encoding)

                # Only flag if fixed has fewer anomalous characters
                if anomalous_in_fixed < anomalous_in_original:
                    suspect_tags[key] = intermediate_bytes

    return suspect_tags


def try_decode(raw_bytes: bytes, encoding: str) -> str | None:
    """Try decoding raw bytes with the given encoding."""
    try:
        return raw_bytes.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return None


def guess_encoding(raw_bytes: bytes) -> list[tuple[str, str, str]]:
    """Try multiple encodings and return plausible results.

    Returns list of (encoding_name, description, decoded_text).
    """
    results = []
    for enc, desc in ENCODINGS.items():
        decoded = try_decode(raw_bytes, enc)
        if decoded:
            results.append((enc, desc, decoded))
    return results


def _count_anomalous_chars(text: str, encoding: str) -> int:
    """Count characters outside the expected Unicode range for the given encoding.

    Lower counts indicate better text quality (fewer anomalies).
    """
    if encoding.startswith("cp1251") or encoding.startswith("koi8"):
        # Basic Russian Cyrillic: U+0410 to U+044F (А-я)
        return sum(1 for c in text if not (0x410 <= ord(c) <= 0x44F))
    elif encoding.startswith("shift_jis") or encoding.startswith("euc-jp"):
        # Japanese Unicode blocks: Hiragana, Katakana, CJK
        return sum(1 for c in text if not (0x3040 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF))
    elif encoding.startswith("gb") or encoding.startswith("big5"):
        # Chinese CJK Unicode block
        return sum(1 for c in text if not (0x4E00 <= ord(c) <= 0x9FFF))
    else:
        # For unknown encodings, return 0 if different from original, else 1
        return 0
