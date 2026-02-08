"""Tag inspection and manipulation commands."""

from pathlib import Path

import mutagen
import typer
from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TDRC, COMM
from rich.progress import Progress, SpinnerColumn, TextColumn

from musictl.core.audio import read_audio
from musictl.core.encoding import detect_non_utf8_tags, guess_encoding, try_decode, ENCODINGS
from musictl.core.scanner import walk_audio_files
from musictl.utils.console import console, make_tag_table


def _parse_id3v1_field(data: bytes, start: int, end: int) -> str:
    """Parse an ID3v1 text field from raw bytes."""
    return data[start:end].rstrip(b"\x00").decode("latin1", errors="ignore")

app = typer.Typer(help="Audio tag operations")


@app.command()
def show(
    path: Path = typer.Argument(..., help="Audio file or directory to inspect"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R", help="Recurse into subdirectories"),
):
    """Display tags for audio files."""
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))
    if not files:
        console.print(f"[warning]No audio files found in {target}[/warning]")
        raise typer.Exit(0)

    for audio_path in files:
        info = read_audio(audio_path)

        if info.error:
            console.print(f"[error]Error reading {audio_path.name}: {info.error}[/error]")
            continue

        # File info header
        rel_path = audio_path.relative_to(target) if target.is_dir() else audio_path.name
        table = make_tag_table(title=str(rel_path))

        # Audio properties
        table.add_row("Format", info.format)
        table.add_row("Sample Rate", info.sample_rate_str)
        if info.bit_depth:
            table.add_row("Bit Depth", f"{info.bit_depth}-bit")
        table.add_row("Channels", str(info.channels))
        table.add_row("Duration", info.duration_str)
        if info.bitrate:
            table.add_row("Bitrate", f"{info.bitrate // 1000} kbps")
        if info.has_id3v1:
            table.add_row("ID3v1", "[warning]Present[/warning]")
        if info.has_id3v2:
            table.add_row("ID3v2", "[success]Present[/success]")

        # Separator
        table.add_row("─" * 20, "─" * 40)

        # Tags
        for key, value in sorted(info.tags.items()):
            table.add_row(key, value)

        console.print(table)
        console.print()


@app.command("fix-encoding")
def fix_encoding(
    path: Path = typer.Argument(..., help="Audio file or directory to fix"),
    source_encoding: str = typer.Option(
        "cp1251", "--from", "-f", help=f"Source encoding ({', '.join(ENCODINGS.keys())})"
    ),
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default is dry-run)"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Fix mojibake (double-encoded text) in ID3 tags.

    This fixes text where UTF-8 bytes were misinterpreted as another encoding
    and re-saved, creating garbled characters (mojibake).

    Example: "Аквариум" (correct) → misread as CP1251 → "РђРєРІР°СЂРёСѓРј" (garbled)

    SAFETY FEATURES:
    - Only fixes text that successfully reverses to better Unicode
    - Skips files where tags are already correct
    - Verifies the fixed text contains more valid characters for the target script
    - Dry-run by default (--apply required to save changes)

    Common use case: Fixing Russian/Cyrillic tags that were double-encoded.
    """
    target = Path(path).expanduser().resolve()

    if source_encoding not in ENCODINGS:
        console.print(f"[error]Unknown encoding: {source_encoding}[/error]")
        console.print(f"[info]Supported: {', '.join(ENCODINGS.keys())}[/info]")
        raise typer.Exit(1)

    files = [f for f in walk_audio_files(target, recursive=recursive) if f.suffix.lower() == ".mp3"]
    if not files:
        console.print("[warning]No MP3 files found (encoding fix only applies to ID3 tags)[/warning]")
        raise typer.Exit(0)

    fixed_count = 0
    skipped_count = 0

    for audio_path in files:
        suspect = detect_non_utf8_tags(audio_path, encoding=source_encoding)
        if not suspect:
            skipped_count += 1
            continue

        rel_path = audio_path.relative_to(target) if target.is_dir() else audio_path.name
        console.print(f"\n[info]File: {rel_path}[/info]")

        try:
            id3 = ID3(str(audio_path))
        except ID3NoHeaderError:
            continue

        changes = []
        for key, intermediate_bytes in suspect.items():
            # suspect contains intermediate bytes from one of two patterns:
            # Pattern 1 (UTF-8 mojibake): intermediate_bytes are encoded in source_encoding
            #            → decode as UTF-8 to get original
            # Pattern 2 (wrong header): intermediate_bytes are Latin-1
            #            → decode as source_encoding to get original

            # Try both decodings and pick the one that works
            try:
                # Pattern 1: UTF-8 mojibake
                decoded = intermediate_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    # Pattern 2: wrong encoding header
                    decoded = intermediate_bytes.decode(source_encoding)
                except UnicodeDecodeError:
                    continue

            current = str(id3.get(key, ""))
            # Sanity check: only apply if result is different
            if decoded == current:
                continue

            changes.append((key, current, decoded))
            console.print(f"  [tag_key]{key}[/tag_key]: [error]{current}[/error] → [success]{decoded}[/success]")

        if changes and apply:
            for key, _old, new_val in changes:
                frame = id3[key]
                frame.text = [new_val]
                frame.encoding = 3  # UTF-8
            id3.save()
            console.print(f"  [success]✓ Saved[/success]")
            fixed_count += 1
        elif changes:
            fixed_count += 1

    console.print()
    if apply:
        console.print(f"[success]Fixed {fixed_count} files, skipped {skipped_count}[/success]")
    else:
        console.print(f"[info]Dry run: {fixed_count} files would be fixed, {skipped_count} already OK[/info]")
        if fixed_count > 0:
            console.print("[info]Run with --apply to save changes[/info]")


@app.command("strip-v1")
def strip_v1(
    path: Path = typer.Argument(..., help="Audio file or directory"),
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default is dry-run)"),
    migrate: bool = typer.Option(False, "--migrate", help="Copy ID3v1 to ID3v2 before stripping"),
    force: bool = typer.Option(False, "--force", help="Strip ID3v1 even if no ID3v2 exists (data loss!)"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Remove ID3v1 tags from MP3 files, keeping only ID3v2.

    By default, skips files with only ID3v1 tags to prevent data loss.
    Use --migrate to copy ID3v1 data to ID3v2 first (safe).
    Use --force to strip even without ID3v2 (dangerous, loses metadata).
    """
    target = Path(path).expanduser().resolve()

    if migrate and force:
        console.print("[error]Cannot use both --migrate and --force[/error]")
        raise typer.Exit(1)

    files = [f for f in walk_audio_files(target, recursive=recursive) if f.suffix.lower() == ".mp3"]
    if not files:
        console.print("[warning]No MP3 files found[/warning]")
        raise typer.Exit(0)

    stripped_count = 0
    skipped_count = 0
    migrated_count = 0

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning for ID3v1 tags...", total=len(files))

            for audio_path in files:
                progress.advance(task)

                # Check for both ID3v1 and ID3v2 in one file open
                has_v1 = False
                has_v2 = False
                try:
                    with open(audio_path, "rb") as f:
                        # Check for ID3v2 at start of file
                        has_v2 = f.read(3) == b"ID3"
                        # Check for ID3v1 at end of file
                        f.seek(-128, 2)
                        has_v1 = f.read(3) == b"TAG"
                except Exception:
                    continue

                if not has_v1:
                    continue

                rel_path = audio_path.relative_to(target) if target.is_dir() else audio_path.name

                # Safety check: only strip if ID3v2 exists, unless --migrate or --force
                if not has_v2 and not migrate and not force:
                    skipped_count += 1
                    if not apply:
                        console.print(f"  [warning]⚠ Only ID3v1 (would skip):[/warning] {rel_path}")
                    else:
                        console.print(f"  [warning]⚠ Skipped (only ID3v1):[/warning] {rel_path}")
                    continue

                # Migrate ID3v1 to ID3v2 if requested
                if migrate and not has_v2 and apply:
                    try:
                        # Read ID3v1 tag (last 128 bytes)
                        with open(audio_path, "rb") as f:
                            f.seek(-128, 2)
                            v1_data = f.read(128)

                        # Parse ID3v1 fields
                        if v1_data[0:3] == b"TAG":
                            title = _parse_id3v1_field(v1_data, 3, 33)
                            artist = _parse_id3v1_field(v1_data, 33, 63)
                            album = _parse_id3v1_field(v1_data, 63, 93)
                            year = _parse_id3v1_field(v1_data, 93, 97)
                            comment = _parse_id3v1_field(v1_data, 97, 127)

                            # Create ID3v2 tags
                            try:
                                id3 = ID3(str(audio_path))
                            except ID3NoHeaderError:
                                id3 = ID3()

                            if title:
                                id3.add(TIT2(encoding=3, text=title))
                            if artist:
                                id3.add(TPE1(encoding=3, text=artist))
                            if album:
                                id3.add(TALB(encoding=3, text=album))
                            if year:
                                id3.add(TDRC(encoding=3, text=year))
                            if comment:
                                id3.add(COMM(encoding=3, lang="eng", desc="", text=comment))

                            id3.save(str(audio_path))
                            migrated_count += 1
                            console.print(f"  [success]→[/success] Migrated ID3v1→ID3v2: {rel_path}")
                    except Exception as e:
                        console.print(f"  [error]✗ Migration failed on {rel_path}: {e}[/error]")
                        continue

                if apply:
                    # Truncate the last 128 bytes (ID3v1 tag)
                    try:
                        size = audio_path.stat().st_size
                        with open(audio_path, "r+b") as f:
                            f.truncate(size - 128)
                        stripped_count += 1
                        if not migrate:
                            console.print(f"  [success]✓[/success] Stripped ID3v1: {rel_path}")
                    except Exception as e:
                        console.print(f"  [error]✗ Error on {rel_path}: {e}[/error]")
                else:
                    stripped_count += 1
                    if has_v2:
                        console.print(f"  [info]Would strip:[/info] {rel_path}")
                    elif migrate:
                        console.print(f"  [info]Would migrate & strip:[/info] {rel_path}")
                    elif force:
                        console.print(f"  [warning]Would force strip:[/warning] {rel_path}")

    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    console.print()
    if apply:
        if migrate and migrated_count > 0:
            console.print(f"[success]Migrated {migrated_count} files from ID3v1 to ID3v2[/success]")
        console.print(f"[success]Stripped ID3v1 from {stripped_count} files[/success]")
        if skipped_count > 0:
            console.print(f"[warning]Skipped {skipped_count} files with only ID3v1 tags[/warning]")
            console.print(f"[info]Use --migrate to copy ID3v1→ID3v2 first, or --force to strip anyway[/info]")
    else:
        console.print(f"[info]Dry run: {stripped_count} files would be processed[/info]")
        if skipped_count > 0:
            console.print(f"[warning]{skipped_count} files would be skipped (only ID3v1)[/warning]")
            console.print(f"[info]Use --migrate to copy ID3v1→ID3v2 first, or --force to strip anyway[/info]")
        if stripped_count > 0:
            console.print("[info]Run with --apply to process them[/info]")


@app.command()
def normalize(
    path: Path = typer.Argument(..., help="Audio file or directory"),
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default is dry-run)"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Normalize common tag inconsistencies.

    Fixes: leading/trailing whitespace, multiple spaces, inconsistent
    'Various Artists' spellings, genre variants, empty tags.
    """
    target = Path(path).expanduser().resolve()
    files = list(walk_audio_files(target, recursive=recursive))
    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    various_artists_variants = {
        "v/a", "v.a.", "va", "various", "various artist",
        "various artists", "variousartists", "v / a", "v/ a",
    }

    # Genre normalization mapping (lowercase variant -> canonical form)
    genre_mappings = {
        # Electronic variants
        "electronic": "Electronic",
        "electro": "Electronic",
        # Hip-Hop variants
        "hip-hop": "Hip-Hop",
        "hip hop": "Hip-Hop",
        "hiphop": "Hip-Hop",
        "rap": "Hip-Hop",
        # Rock variants
        "rock": "Rock",
        "rock & roll": "Rock & Roll",
        "rock and roll": "Rock & Roll",
        "rock'n'roll": "Rock & Roll",
        # Pop variants
        "pop": "Pop",
        # Jazz variants
        "jazz": "Jazz",
        # Classical variants
        "classical": "Classical",
        "classic": "Classical",
        # Metal variants
        "metal": "Metal",
        "heavy metal": "Heavy Metal",
        # Alternative variants
        "alternative": "Alternative",
        "alt": "Alternative",
        "indie": "Indie",
        # R&B variants
        "r&b": "R&B",
        "r & b": "R&B",
        "rnb": "R&B",
        "rhythm and blues": "R&B",
        # Country variants
        "country": "Country",
        # Blues variants
        "blues": "Blues",
        # Punk variants
        "punk": "Punk",
        "punk rock": "Punk Rock",
        # Reggae variants
        "reggae": "Reggae",
        # Soul variants
        "soul": "Soul",
        # Folk variants
        "folk": "Folk",
        # Experimental variants
        "experimental": "Experimental",
        # Ambient variants
        "ambient": "Ambient",
    }

    fixed_count = 0

    for audio_path in files:
        try:
            mfile = mutagen.File(str(audio_path), easy=True)
        except Exception:
            continue
        if mfile is None or mfile.tags is None:
            continue

        changes = []
        for key in list(mfile.tags.keys()):
            values = mfile.tags[key]
            new_values = []
            for val in values:
                original = val
                # Strip whitespace
                val = val.strip()
                # Collapse multiple spaces
                val = " ".join(val.split())
                # Normalize Various Artists
                if key.lower() in ("artist", "albumartist", "album_artist"):
                    if val.lower().strip() in various_artists_variants:
                        val = "Various Artists"
                # Normalize genre
                if key.lower() == "genre":
                    val_lower = val.lower().strip()
                    if val_lower in genre_mappings:
                        val = genre_mappings[val_lower]
                    else:
                        # Default: titlecase for unmapped genres
                        val = val.title()
                # Track changes
                if val != original:
                    changes.append((key, original, val))
                # Skip empty tags
                if val:
                    new_values.append(val)

            if new_values != list(mfile.tags[key]):
                mfile.tags[key] = new_values

        if changes:
            fixed_count += 1
            rel_path = audio_path.relative_to(target) if target.is_dir() else audio_path.name
            console.print(f"\n[info]File: {rel_path}[/info]")
            for key, old, new in changes:
                console.print(f"  [tag_key]{key}[/tag_key]: [error]{old!r}[/error] → [success]{new!r}[/success]")

            if apply:
                mfile.save()
                console.print(f"  [success]✓ Saved[/success]")

    console.print()
    if apply:
        console.print(f"[success]Normalized tags in {fixed_count} files[/success]")
    else:
        console.print(f"[info]Dry run: {fixed_count} files would be normalized[/info]")
        if fixed_count > 0:
            console.print("[info]Run with --apply to save changes[/info]")
