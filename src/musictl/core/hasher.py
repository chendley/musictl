"""File hashing for duplicate detection."""

import hashlib
from pathlib import Path

CHUNK_SIZE = 8192


def file_hash(path: Path, algorithm: str = "sha256") -> str:
    """Compute hash of a file's contents."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def quick_hash(path: Path) -> str:
    """Quick hash using file size + first/last 8KB for fast dedup."""
    size = path.stat().st_size
    h = hashlib.sha256()
    h.update(str(size).encode())

    with open(path, "rb") as f:
        h.update(f.read(CHUNK_SIZE))
        if size > CHUNK_SIZE * 2:
            f.seek(-CHUNK_SIZE, 2)
            h.update(f.read(CHUNK_SIZE))

    return h.hexdigest()
