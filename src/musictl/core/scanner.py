"""Directory walker with audio file filtering."""

from collections.abc import Iterator
from pathlib import Path

from musictl.core.audio import SUPPORTED_EXTENSIONS


def walk_audio_files(root: Path, recursive: bool = True) -> Iterator[Path]:
    """Yield audio files from a directory.

    If root is a file, yields it directly if it's a supported format.
    """
    if root.is_file():
        if root.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield root
        return

    if recursive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                yield path
    else:
        for path in sorted(root.iterdir()):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                yield path
