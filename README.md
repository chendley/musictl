# musictl

**CLI toolkit for managing, fixing, and organizing music libraries.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Tests: 167 passing](https://img.shields.io/badge/tests-167%20passing-brightgreen.svg)]()

Command-line tool for cleaning up tags, finding duplicates, organizing files, and validating audio collections.

---

## Safety

**Default behavior:**

- ✅ **Dry-run by default** - Destructive operations preview changes
- ✅ **Explicit `--apply` required** - No accidental modifications
- ✅ **Safety checks** - ID3v1 stripping verifies ID3v2 exists first
- ✅ **Local-only** - No network access, no telemetry
- ✅ **167 tests** - Comprehensive test coverage
- ✅ **Security reviewed** - See [SECURITY.md](SECURITY.md)

**Backup your library before bulk operations.**

## Features

### Tag Management
- **Fix encoding issues** - Convert CP1251/KOI-8/other legacy encodings to UTF-8
- **Remove ID3v1 tags** - Strip obsolete tags from MP3 files
- **Normalize tags** - Clean up whitespace, standardize "Various Artists"
- **Display metadata** - View all tags and audio properties

### Library Scanning
- **Full library statistics** - Format distribution, sample rates, bit depths
- **Find missing tags** - Detect files with incomplete metadata
- **Export scan results** - CSV and JSON export for all scan commands
- **Find hi-res files** - Detect files above specified sample rate
- **Detect encoding issues** - Find non-UTF-8 encoded tags

### File Organization
- **Organize by format** - Sort into FLAC/, MP3/, OGG/ directories
- **Organize by sample rate** - Separate hi-res files from standard

### Duplicates & Validation
- **Exact duplicate detection** - Find identical files (byte-level)
- **Fuzzy duplicate matching** - Find same song in different formats
- **File integrity validation** - Detect corrupted or unreadable files

### Cleanup Operations
- **Remove temporary files** - Delete OS-generated junk (.DS_Store, Thumbs.db, ._ files, etc.)
- **Cross-platform** - Handles macOS, Windows, and Linux temporary files

## Installation

### Option 1: Install with uv (Recommended)

[uv](https://github.com/astral-sh/uv) installs musictl in an isolated environment:

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install musictl
uv tool install musictl

# Verify installation
musictl --version
```

### Option 2: Install with pip

```bash
# Install from PyPI (when published)
pip install musictl

# Or install from source
git clone https://github.com/caseyhendley/musictl.git
cd musictl
pip install .
```

### Option 3: Run from source (Development)

```bash
git clone https://github.com/caseyhendley/musictl.git
cd musictl
uv run musictl --help
```

### System Requirements

- **Python**: 3.12 or higher
- **ffprobe** (optional): For advanced audio analysis (sample rate, bit depth)
  ```bash
  # Install ffmpeg (includes ffprobe)
  # Ubuntu/Debian:
  sudo apt install ffmpeg

  # macOS:
  brew install ffmpeg

  # Fedora:
  sudo dnf install ffmpeg
  ```

### Verifying Installation

```bash
# Check version
musictl --version

# View help
musictl --help

# Test on a single file (safe, read-only)
musictl tags show /path/to/song.mp3
```

## Getting Started

**Basic workflow:**

1. **Backup your library**
   ```bash
   rsync -av ~/Music /mnt/backup/Music
   ```

2. **Scan your library**
   ```bash
   musictl scan library ~/Music
   ```

3. **Preview changes** (dry-run, default behavior)
   ```bash
   musictl tags strip-v1 ~/Music
   ```

4. **Apply changes** (requires `--apply` flag)
   ```bash
   musictl tags strip-v1 ~/Music --apply
   ```

### Dry-Run vs Apply

**Dry-run (default):** Shows what would happen, makes no changes
```bash
musictl dupes find ~/Music              # Preview only
```

**Apply mode:** Makes changes (requires `--apply`)
```bash
musictl dupes find ~/Music --apply      # Deletes files
```

---

## Quick Start

### View Tags
```bash
# Show tags for a single file
musictl tags show song.mp3

# Show tags for all files in a directory
musictl tags show ~/Music
```

### Fix Encoding Issues
```bash
# Preview encoding fixes (dry-run by default)
musictl tags fix-encoding ~/Music --from cp1251

# Apply the fixes
musictl tags fix-encoding ~/Music --from cp1251 --apply
```

### Scan Your Library
```bash
# Full library scan with statistics
musictl scan library ~/Music

# Export scan results to CSV
musictl scan library ~/Music --export library_stats.csv --format csv

# Export scan results to JSON
musictl scan library ~/Music --export library_stats.json --format json

# Find files with missing tags (artist, album, title, year)
musictl scan missing ~/Music

# Export missing tags list
musictl scan missing ~/Music --export missing_tags.csv

# Find hi-res files (>48kHz)
musictl scan hires ~/Music

# Export hi-res file list
musictl scan hires ~/Music --export hires_files.csv

# Find files with encoding issues
musictl scan encoding ~/Music

# Export encoding issues list
musictl scan encoding ~/Music --export encoding_issues.json --format json
```

### Find Duplicates

**CAUTION**: Duplicate deletion is PERMANENT. Always review dry-run first!

```bash
# Find exact duplicates (safe dry-run)
musictl dupes find ~/Music

# Find fuzzy duplicates (metadata-based, safe dry-run)
musictl dupes find ~/Music --fuzzy

# DANGER: Delete duplicates (keeps one copy, deletes others)
# Review the dry-run output first!
musictl dupes find ~/Music --apply
```

### Organize Files
```bash
# Organize by format (preview)
musictl organize by-format ~/Music --dest ~/Music/Organized

# Organize by format (execute)
musictl organize by-format ~/Music --dest ~/Music/Organized --apply

# Separate hi-res files
musictl organize by-samplerate ~/Music --dest ~/Music/HiRes --apply
```

### Validate Files
```bash
# Check file integrity
musictl validate check ~/Music

# Verbose output (show all files)
musictl validate check ~/Music --verbose
```

### Clean Temporary Files
```bash
# Preview cleanup (dry-run)
musictl clean temp-files ~/Music

# Remove temporary files
musictl clean temp-files ~/Music --apply

# Non-recursive cleanup (current directory only)
musictl clean temp-files ~/Music --no-recursive --apply
```

## Configuration

Create a config file for default settings:

```bash
musictl config init
```

This creates `~/.config/musictl/config.toml`:

```toml
[encoding]
default_source = "cp1251"

[scan]
hires_threshold = 48000

[dupes]
default_mode = "exact"

[general]
dry_run = true
recursive = true
```

View your config:
```bash
musictl config show
```

## Command Reference

### Tags

| Command | Description |
|---------|-------------|
| `musictl tags show <path>` | Display tags and metadata |
| `musictl tags fix-encoding <path> --from <encoding>` | Fix character encoding (CP1251→UTF-8) |
| `musictl tags strip-v1 <path>` | Remove ID3v1 tags from MP3s (with safety checks) |
| `musictl tags normalize <path>` | Clean up tag inconsistencies |

**ID3v1 Stripping Safety** - Protection against metadata loss:

| Mode | Behavior | Safety | Use When |
|------|----------|--------|----------|
| Default (no flags) | Skip files with only ID3v1 | ✅ Safe | You only want to strip files that already have ID3v2 |
| `--migrate` | Copy ID3v1 → ID3v2, then strip | ✅ Safe | You want to upgrade all files to ID3v2 (recommended) |
| `--force` | Strip ID3v1 even without ID3v2 | 🔴 Dangerous | You want to delete metadata (rarely needed) |

**Example workflow** (safest approach):
```bash
# 1. See what will happen (dry-run)
musictl tags strip-v1 ~/Music --migrate

# 2. Apply migration (safe - preserves all metadata)
musictl tags strip-v1 ~/Music --apply --migrate

# Result: All ID3v1 tags migrated to ID3v2, then stripped
#         Zero data loss!
```

**Common encodings**: `cp1251`, `koi8-r`, `koi8-u`, `iso-8859-1`, `shift_jis`, `gb2312`, `euc-kr`

### Scanning

| Command | Description |
|---------|-------------|
| `musictl scan library <path>` | Full library statistics |
| `musictl scan hires <path>` | Find hi-res files (>48kHz default) |
| `musictl scan encoding <path>` | Find non-UTF-8 tags |

Options:
- `--threshold <hz>` - Custom sample rate threshold for hi-res
- `--recursive` / `--no-recursive` - Control directory recursion

### Organization

| Command | Description |
|---------|-------------|
| `musictl organize by-format <path> --dest <dir>` | Sort by format (FLAC/, MP3/, etc.) |
| `musictl organize by-samplerate <path> --dest <dir>` | Separate hi-res files |

Options:
- `--apply` - Execute the move (default is dry-run)
- `--threshold <hz>` - Custom sample rate threshold

### Duplicates

| Command | Description |
|---------|-------------|
| `musictl dupes find <path>` | Find exact duplicates (byte-level) |
| `musictl dupes find <path> --fuzzy` | Find fuzzy duplicates (metadata) |

Options:
- `--apply` - Delete duplicates (keeps first file)

**CRITICAL WARNING**:
- Deletion is **PERMANENT** - deleted files cannot be recovered!
- Always run WITHOUT `--apply` first to review duplicates
- Duplicate detection keeps the **first file** in each group
- File order may vary between runs - be careful!

**Recommended workflow**:
```bash
# 1. Find duplicates (safe)
musictl dupes find ~/Music > duplicates.txt

# 2. Review the output carefully
less duplicates.txt

# 3. If you're absolutely sure, apply
musictl dupes find ~/Music --apply
```

### Validation

| Command | Description |
|---------|-------------|
| `musictl validate check <path>` | Verify file integrity |

Options:
- `--verbose` - Show per-file validation status

### Cleanup

| Command | Description |
|---------|-------------|
| `musictl clean temp-files <path>` | Remove OS-generated temporary files |

Options:
- `--apply` - Execute the deletion (default is dry-run)
- `--recursive` / `--no-recursive` - Control directory recursion

**Files Removed** (safe to delete):
- **macOS**: `.DS_Store`, `._*` (resource forks), `.AppleDouble`, `.Spotlight-V100`, `.Trashes`
- **Windows**: `Thumbs.db`, `desktop.ini`
- **Linux**: `.directory` (KDE folder metadata)
- **Generic**: `*.tmp`, `*.bak`

**Safety Notes**:
- ✅ Only removes known temporary file patterns
- ✅ Never touches actual music files
- ✅ Dry-run by default - shows what will be deleted
- ⚠️ Deletion is permanent - review dry-run output first!

**Example**:
```bash
# Safe: See what would be deleted
musictl clean temp-files ~/Music

# Shows: "Found 266 temporary files: .DS_Store: 13 files, ._*: 239 files..."

# If output looks correct, apply
musictl clean temp-files ~/Music --apply
```

### Configuration

| Command | Description |
|---------|-------------|
| `musictl config init` | Create default config file |
| `musictl config show` | Show current configuration |
| `musictl config path` | Show config file location |

## Safety Features

### Built-in Protection

- ✅ **Dry-run by default** - All destructive operations require explicit `--apply`
- ✅ **Preview before execution** - See exactly what will happen before committing
- ✅ **Graceful cancellation** - Ctrl+C cleanly exits without corruption
- ✅ **Smart duplicate selection** - Keeps highest quality files (by bitrate/sample rate)
- ✅ **ID3v1 migration safety** - Checks for ID3v2 tags before stripping ID3v1
- ✅ **Path validation** - Prevents path traversal attacks
- ✅ **No command injection** - Safe subprocess handling
- ✅ **Permission respect** - Won't modify files you don't have permission to change

### Safety Flags

| Flag | Purpose | Risk Level |
|------|---------|------------|
| *(no flag)* | Dry-run mode - NO changes made | ✅ Safe |
| `--apply` | Execute changes | ⚠️ Caution required |
| `--migrate` | Copy ID3v1 → ID3v2 before stripping | ✅ Safe (preserves data) |
| `--force` | Skip safety checks | 🔴 Dangerous (data loss possible) |

### What Could Go Wrong?

**Potential Risks** (and how we mitigate them):

1. **Accidental file deletion**
   - ✅ Mitigated: Dry-run by default, requires `--apply`
   - ✅ Mitigated: Clear warnings before destructive operations

2. **Metadata loss**
   - ✅ Mitigated: `strip-v1` checks for ID3v2 before stripping ID3v1
   - ✅ Mitigated: `--migrate` flag copies tags before deletion
   - ✅ Mitigated: Dry-run shows which files would be skipped

3. **File corruption**
   - ✅ Mitigated: Operations are atomic where possible
   - ✅ Mitigated: Mutagen library handles tag writes safely
   - ⚠️ **User responsibility**: Don't run multiple operations on same files concurrently

4. **Processing wrong directory**
   - ✅ Mitigated: Dry-run shows full paths before execution
   - ⚠️ **User responsibility**: Double-check paths before `--apply`

### Best Practices

1. **Always test on a copy first**
   ```bash
   cp -r ~/Music/TestAlbum /tmp/test
   musictl tags strip-v1 /tmp/test --apply
   ```

2. **Use version control for critical collections**
   ```bash
   cd ~/Music
   git init
   git add .
   git commit -m "Backup before musictl operations"
   ```

3. **Review dry-run output carefully**
   - Check file counts match expectations
   - Verify paths are correct
   - Look for unexpected files in the list

4. **Start small, then scale up**
   - Test on one album → one artist → full library

5. **Keep backups**
   - External drive backups
   - Cloud storage (Backblaze, etc.)
   - RAID arrays for redundancy

## Supported Formats

- **MP3** - Full ID3v1/v2 support
- **FLAC** - Vorbis comments, hi-res detection
- **OGG** - Vorbis comments
- **Opus** - Full support
- **M4A** - AAC/ALAC support
- **WMA** - Windows Media Audio
- **WAV** - Basic support
- **AIFF** - Apple audio format

## Testing

musictl has 146 comprehensive tests covering all features:

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=musictl
```

---

## Troubleshooting

### Permission Errors

```
Error: Permission denied
```

**Solution**: Ensure you have write permissions on the files:
```bash
# Check file permissions
ls -l ~/Music/file.mp3

# Fix permissions if needed (be careful!)
chmod u+w ~/Music/file.mp3
```

### ffprobe Not Found

```
Warning: ffprobe not found
```

**Impact**: Sample rate and bit depth detection will be limited to what mutagen can detect.

**Solution**: Install ffmpeg (see Installation section above)

### Files Not Found or Skipped

```
Warning: No MP3 files found
```

**Causes**:
1. Wrong directory path
2. Files have uppercase extensions (.MP3 vs .mp3)
3. Files are in subdirectories (use `--recursive`)

**Solution**:
```bash
# Check if files exist
ls ~/Music/*.mp3

# Use recursive flag
musictl tags strip-v1 ~/Music --recursive
```

### ID3v1 Tags Not Stripped

```
Skipped 150 files with only ID3v1 tags
```

**This is INTENTIONAL** - musictl protects you from data loss!

**Solution**: Use `--migrate` to copy ID3v1 → ID3v2 first:
```bash
musictl tags strip-v1 ~/Music --apply --migrate
```

### Operation Too Slow

**Causes**: Large library, slow disk, or network-mounted files

**Solutions**:
1. Process subdirectories separately
2. Use `--no-recursive` for top-level only
3. Exclude slow network drives

---

## FAQ

### Is musictl safe to use?

Safe when used properly:
- ✅ Dry-run by default
- ✅ 146 tests
- ✅ Security reviewed (see [SECURITY.md](SECURITY.md))
- ⚠️ Backup before bulk operations

### Will it corrupt my files?

Unlikely:
- Uses mutagen library (stable, widely used)
- Operations are atomic where possible
- ⚠️ Don't run concurrent operations on same files

### Can I undo changes?

**Some operations are reversible, some are not:**

| Operation | Reversible? | How to Undo |
|-----------|-------------|-------------|
| `tags strip-v1` | ❌ No | ID3v1 data lost forever (use `--migrate` instead!) |
| `tags fix-encoding` | ⚠️ Partially | Original encoding lost, but text preserved |
| `dupes find --apply` | ❌ No | Files deleted permanently |
| `clean temp-files` | ❌ No | Files deleted permanently |
| `organize` | ✅ Yes | Files moved, not modified (move them back) |
| `validate` | ✅ Yes | Read-only operation |

**Best protection**: Keep backups!

### Does it phone home or collect data?

**No**:
- ✅ Zero network access
- ✅ No telemetry
- ✅ No analytics
- ✅ No updates checking
- ✅ 100% local operation

### What if I find a bug?

1. Check if it's already reported: [GitHub Issues](https://github.com/caseyhendley/musictl/issues)
2. Include: Command run, error message, Python version, OS
3. For security issues: See [SECURITY.md](SECURITY.md) for responsible disclosure

### Can I use this on network/cloud storage?

**Yes, but with caution**:
- ⚠️ Operations may be slower
- ⚠️ Network interruptions could cause issues
- ⚠️ Concurrent access from multiple machines is risky

**Recommendation**: Work on local copies, then sync to cloud.

### Does it support Windows/macOS/Linux?

**Yes**, musictl is cross-platform:
- ✅ Linux (tested on Fedora, Ubuntu, Debian)
- ✅ macOS (tested on Big Sur+)
- ✅ Windows (tested on Windows 10+)

**Note**: Some features require ffmpeg (optional)

### How do I contribute?

See [Contributing](#contributing) section below.

---

## Security

For a comprehensive security analysis, see [SECURITY.md](SECURITY.md).

**Summary**:
- ✅ No command injection vulnerabilities
- ✅ Path traversal protection
- ✅ Safe subprocess handling
- ✅ Well-vetted dependencies
- ⚠️ Minor TOCTOU risk in concurrent scenarios (low probability)
- ⚠️ Symlinks are followed (documented behavior)

**For security issues**: See [SECURITY.md](SECURITY.md) for responsible disclosure process.

## When NOT to Use musictl

**Do NOT use musictl for:**

1. **Untrusted files** - Files from unknown sources may contain malformed metadata that could expose bugs in the parsing library
2. **Production servers** - Not designed for server/daemon operation
3. **Concurrent processing** - Don't run multiple musictl operations on the same files simultaneously (TOCTOU risk)
4. **Network filesystems under heavy use** - Risk of corruption if network interrupts during write
5. **Files you don't own** - Respect file permissions and ownership

**Use with caution for:**

- Files on network/cloud storage (slower, network dependency)
- Very large libraries (>100k files) - may take considerable time
- Files with read-only permissions (will fail, but safely)

---

## Contributing

Contributions welcome! Areas for improvement:

- Additional audio formats
- More organization patterns
- Advanced duplicate detection
- Batch operations
- Plugin system

## License

GNU General Public License v3.0 or later (GPLv3+) - see [LICENSE](LICENSE) file.

**This means**:
- ✅ You can use, modify, and distribute this software freely
- ✅ You can use it commercially
- ⚠️ If you distribute modified versions, you MUST:
  - Release source code under GPLv3
  - Keep the same license (copyleft)
  - Document changes made
- ❌ You CANNOT make closed-source commercial versions

**Why GPLv3?** To ensure musictl remains free and open-source forever, preventing commercial exploitation.

## Acknowledgments

Built with:
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting
- [Mutagen](https://mutagen.readthedocs.io/) - Audio metadata

---

**Music library management tool**
