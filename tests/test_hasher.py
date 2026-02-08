"""Tests for core.hasher module."""

import hashlib
from pathlib import Path

import pytest

from musictl.core.hasher import file_hash, quick_hash, CHUNK_SIZE


def test_file_hash_identical_files(temp_music_dir):
    """Test that identical files produce identical hashes."""
    file1 = temp_music_dir / "file1.txt"
    file2 = temp_music_dir / "file2.txt"

    content = b"Hello, World!" * 1000
    file1.write_bytes(content)
    file2.write_bytes(content)

    hash1 = file_hash(file1)
    hash2 = file_hash(file2)

    assert hash1 == hash2


def test_file_hash_different_files(temp_music_dir):
    """Test that different files produce different hashes."""
    file1 = temp_music_dir / "file1.txt"
    file2 = temp_music_dir / "file2.txt"

    file1.write_bytes(b"Content A")
    file2.write_bytes(b"Content B")

    hash1 = file_hash(file1)
    hash2 = file_hash(file2)

    assert hash1 != hash2


def test_file_hash_default_algorithm(temp_music_dir):
    """Test that default algorithm is SHA256."""
    file = temp_music_dir / "file.txt"
    content = b"Test content"
    file.write_bytes(content)

    hash_result = file_hash(file)

    # SHA256 produces 64 hex characters
    assert len(hash_result) == 64
    assert all(c in "0123456789abcdef" for c in hash_result)

    # Verify it matches manual SHA256
    expected = hashlib.sha256(content).hexdigest()
    assert hash_result == expected


def test_file_hash_custom_algorithm(temp_music_dir):
    """Test using a different hash algorithm."""
    file = temp_music_dir / "file.txt"
    content = b"Test content"
    file.write_bytes(content)

    hash_md5 = file_hash(file, algorithm="md5")

    # MD5 produces 32 hex characters
    assert len(hash_md5) == 32

    expected = hashlib.md5(content).hexdigest()
    assert hash_md5 == expected


def test_file_hash_large_file(temp_music_dir):
    """Test hashing a file larger than CHUNK_SIZE."""
    file = temp_music_dir / "large.bin"

    # Create a file larger than CHUNK_SIZE (8KB)
    content = b"X" * (CHUNK_SIZE * 3)
    file.write_bytes(content)

    hash_result = file_hash(file)

    # Should still produce correct hash
    expected = hashlib.sha256(content).hexdigest()
    assert hash_result == expected


def test_quick_hash_identical_files(temp_music_dir):
    """Test that identical files produce identical quick hashes."""
    file1 = temp_music_dir / "file1.bin"
    file2 = temp_music_dir / "file2.bin"

    content = b"Data" * 5000
    file1.write_bytes(content)
    file2.write_bytes(content)

    qhash1 = quick_hash(file1)
    qhash2 = quick_hash(file2)

    assert qhash1 == qhash2


def test_quick_hash_different_size(temp_music_dir):
    """Test that files of different sizes have different quick hashes."""
    file1 = temp_music_dir / "small.bin"
    file2 = temp_music_dir / "large.bin"

    file1.write_bytes(b"A" * 100)
    file2.write_bytes(b"A" * 200)

    qhash1 = quick_hash(file1)
    qhash2 = quick_hash(file2)

    assert qhash1 != qhash2


def test_quick_hash_different_start(temp_music_dir):
    """Test that files with different starts have different quick hashes."""
    file1 = temp_music_dir / "file1.bin"
    file2 = temp_music_dir / "file2.bin"

    # Same size, different first chunk
    file1.write_bytes(b"A" * 20000)
    file2.write_bytes(b"B" * 20000)

    qhash1 = quick_hash(file1)
    qhash2 = quick_hash(file2)

    assert qhash1 != qhash2


def test_quick_hash_different_end(temp_music_dir):
    """Test that files with different ends have different quick hashes."""
    file1 = temp_music_dir / "file1.bin"
    file2 = temp_music_dir / "file2.bin"

    # Same size and start, different end
    content1 = b"X" * 20000 + b"A" * 1000
    content2 = b"X" * 20000 + b"B" * 1000

    file1.write_bytes(content1)
    file2.write_bytes(content2)

    qhash1 = quick_hash(file1)
    qhash2 = quick_hash(file2)

    assert qhash1 != qhash2


def test_quick_hash_small_file(temp_music_dir):
    """Test quick hash on a small file (less than 2*CHUNK_SIZE)."""
    file = temp_music_dir / "small.bin"
    content = b"Small content"
    file.write_bytes(content)

    qhash = quick_hash(file)

    # Should still produce a valid hash
    assert len(qhash) == 64  # SHA256 hex length
    assert all(c in "0123456789abcdef" for c in qhash)


def test_quick_hash_empty_file(temp_music_dir):
    """Test quick hash on an empty file."""
    file = temp_music_dir / "empty.bin"
    file.write_bytes(b"")

    qhash = quick_hash(file)

    # Should handle empty file gracefully
    assert isinstance(qhash, str)
    assert len(qhash) == 64


def test_quick_hash_vs_full_hash_large_file(temp_music_dir):
    """Test that quick hash is different from full hash for large files."""
    file = temp_music_dir / "large.bin"
    content = b"X" * 100000  # Large file

    file.write_bytes(content)

    qhash = quick_hash(file)
    fhash = file_hash(file)

    # Quick hash should be different (faster but less accurate)
    assert qhash != fhash


def test_chunk_size_constant():
    """Test that CHUNK_SIZE is set to expected value."""
    assert CHUNK_SIZE == 8192
