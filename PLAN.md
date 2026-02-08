# musictl - Music Library Toolkit

## Overview
A Python CLI tool for managing, fixing, and organizing music libraries. FOSS (MIT or GPL), designed to solve real pain points with music collections.

## Tech Stack
- **Python 3.12+**
- **uv** - package/project manager
- **Typer** - CLI framework (with Rich integration)
- **Rich** - terminal UI (progress bars, tables, colored output)
- **mutagen** - audio tag reading/writing (MP3, FLAC, OGG, etc.)
- **ffprobe** (via subprocess) - audio stream analysis (sample rate, bit depth)

## Project Structure

```
~/src/musictl/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── musictl/
│       ├── __init__.py
│       ├── cli.py              # Typer app, command definitions
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── tags.py         # Tag fixing commands (encoding, strip v1, normalize)
│       │   ├── organize.py     # File organization commands (by format, sample rate)
│       │   ├── duplicates.py   # Duplicate detection (byte-level, fuzzy)
│       │   ├── scan.py         # Library scanning and reporting
│       │   └── validate.py     # File integrity validation
│       ├── core/
│       │   ├── __init__.py
│       │   ├── audio.py        # Audio file abstraction (wraps mutagen + ffprobe)
│       │   ├── encoding.py     # Character encoding detection and conversion
│       │   ├── scanner.py      # Directory walker with filtering
│       │   └── hasher.py       # File hashing for duplicate detection
│       └── utils/
│           ├── __init__.py
│           ├── console.py      # Rich console setup, shared output helpers
│           └── config.py       # User config (~/.config/musictl/config.toml)
└── tests/
    ├── __init__.py
    ├── conftest.py             # Shared fixtures (temp dirs with test audio files)
    ├── test_tags.py
    ├── test_organize.py
    ├── test_duplicates.py
    └── test_encoding.py
```

## CLI Commands (Phase 1 - MVP)

```bash
# Tag operations
musictl tags fix-encoding <path> --from cp1251    # Fix encoding (CP1251/KOI-8 → UTF-8)
musictl tags strip-v1 <path>                      # Remove ID3v1 tags
musictl tags normalize <path>                     # Normalize artist/album tags
musictl tags show <path>                          # Display all tags for a file/dir

# Scanning / reporting
musictl scan <path>                               # Full library scan with stats
musictl scan hires <path>                         # Find hi-res files (>48kHz)
musictl scan encoding <path>                      # Detect non-UTF-8 tags

# Organization
musictl organize by-format <path> --dest <dir>    # Move files by format (FLAC/MP3)
musictl organize by-samplerate <path> --dest <dir> # Move hi-res to separate dir

# Duplicates
musictl dupes find <path>                         # Find duplicates (byte-level)
musictl dupes find <path> --fuzzy                 # Fuzzy match by tags/duration

# Validation
musictl validate <path>                           # Check file integrity
```

## Key Design Decisions

1. **Dry-run by default** - All destructive operations (move, delete, modify tags) show a preview and require `--apply` flag to execute. Safety first.
2. **Rich output** - Progress bars for long scans, tables for results, colored diffs for tag changes.
3. **No AI dependency** - Pure Python tool, no API calls needed. This keeps it zero-cost to run.
4. **Idempotent** - Running the same command twice produces the same result.
5. **Respects filesystem** - Uses safe move operations, never deletes without explicit confirmation.

## Implementation Phases

### Phase 1: Project scaffolding + core infrastructure
- Initialize uv project with pyproject.toml
- Set up src layout, CLI entry point
- Core audio file abstraction (mutagen + ffprobe wrapper)
- Rich console setup
- `musictl tags show` command (read-only, prove the stack works)

### Phase 2: Tag operations
- Encoding detection and fix (`tags fix-encoding`)
- ID3v1 stripping (`tags strip-v1`)
- Tag normalization (`tags normalize`)
- Encoding scan (`scan encoding`)

### Phase 3: Scanning and organization
- Library scanner with stats (`scan`)
- Hi-res detection (`scan hires`)
- Format-based organization (`organize by-format`)
- Sample rate organization (`organize by-samplerate`)

### Phase 4: Duplicates and validation
- Byte-level duplicate detection (`dupes find`)
- Fuzzy duplicate matching (`dupes find --fuzzy`)
- File integrity validation (`validate`)

### Phase 5: Polish
- User config file support (~/.config/musictl/config.toml)
- PyPI packaging
- Tests
- README with examples

## Verification
- `uv run musictl --help` shows all commands
- `uv run musictl tags show ~/Music/some-file.flac` displays tags correctly
- `uv run musictl scan ~/Music` produces a library report
- `uv run pytest` passes all tests
