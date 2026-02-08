"""Duplicate file detection commands."""

from collections import defaultdict
from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table

from musictl.core.audio import read_audio
from musictl.core.hasher import file_hash, quick_hash
from musictl.core.scanner import walk_audio_files
from musictl.utils.console import console

app = typer.Typer(help="Duplicate detection operations")


@app.command()
def find(
    path: Path = typer.Argument(..., help="Directory to scan for duplicates"),
    fuzzy: bool = typer.Option(False, "--fuzzy", help="Use fuzzy matching (metadata-based)"),
    apply: bool = typer.Option(False, "--apply", help="Delete duplicates (keeps one copy)"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Find duplicate audio files (byte-level or fuzzy matching)."""
    if fuzzy:
        _find_fuzzy_duplicates(path, apply, recursive)
    else:
        _find_exact_duplicates(path, apply, recursive)


def _find_exact_duplicates(path: Path, apply: bool, recursive: bool):
    """Find exact duplicate files using file hashing."""
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))

    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    console.print(f"\n[info]Scanning {len(files)} files for duplicates...[/info]")

    # Phase 1: Quick hash to reduce comparison set
    quick_hashes = {}
    quick_groups = defaultdict(list)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Computing quick hashes...", total=len(files))

            for audio_path in files:
                progress.advance(task)
                try:
                    qhash = quick_hash(audio_path)
                    quick_hashes[audio_path] = qhash
                    quick_groups[qhash].append(audio_path)
                except Exception as e:
                    console.print(f"[error]Error hashing {audio_path.name}: {e}[/error]")

    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    # Phase 2: Full hash only for files with matching quick hashes
    potential_duplicates = [group for group in quick_groups.values() if len(group) > 1]

    if not potential_duplicates:
        console.print("\n[success]No duplicates found![/success]")
        return

    duplicate_groups = defaultdict(list)

    console.print(f"\n[info]Verifying {sum(len(g) for g in potential_duplicates)} potential duplicates...[/info]")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            total_to_verify = sum(len(group) for group in potential_duplicates)
            task = progress.add_task("Computing full hashes...", total=total_to_verify)

            for group in potential_duplicates:
                for audio_path in group:
                    progress.advance(task)
                    try:
                        fhash = file_hash(audio_path)
                        duplicate_groups[fhash].append(audio_path)
                    except Exception as e:
                        console.print(f"[error]Error hashing {audio_path.name}: {e}[/error]")

    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    # Filter to only actual duplicates
    duplicates = {h: files for h, files in duplicate_groups.items() if len(files) > 1}

    if not duplicates:
        console.print("\n[success]No duplicates found![/success]")
        return

    # Display results
    console.print()
    total_duplicates = sum(len(files) - 1 for files in duplicates.values())
    total_wasted_space = 0

    table = Table(title=f"Duplicate Files ({len(duplicates)} groups)", show_header=True, header_style="bold magenta")
    table.add_column("Group", style="cyan", justify="right")
    table.add_column("Files", justify="right")
    table.add_column("File Size", justify="right")
    table.add_column("Wasted Space", justify="right")

    for i, (hash_val, file_group) in enumerate(sorted(duplicates.items()), 1):
        file_size = file_group[0].stat().st_size
        wasted = file_size * (len(file_group) - 1)
        total_wasted_space += wasted

        # Format sizes
        if file_size >= 1024**3:
            size_str = f"{file_size / 1024**3:.2f} GB"
        elif file_size >= 1024**2:
            size_str = f"{file_size / 1024**2:.2f} MB"
        else:
            size_str = f"{file_size / 1024:.2f} KB"

        if wasted >= 1024**3:
            wasted_str = f"{wasted / 1024**3:.2f} GB"
        elif wasted >= 1024**2:
            wasted_str = f"{wasted / 1024**2:.2f} MB"
        else:
            wasted_str = f"{wasted / 1024:.2f} KB"

        table.add_row(str(i), str(len(file_group)), size_str, wasted_str)

        # Show file paths
        console.print(f"\n[bold cyan]Group {i}:[/bold cyan]")
        for j, file_path in enumerate(sorted(file_group), 1):
            rel_path = file_path.relative_to(target) if target.is_dir() else file_path.name
            marker = "[dim](keep)[/dim]" if j == 1 else "[warning](duplicate)[/warning]"
            console.print(f"  {j}. {rel_path} {marker}")

    console.print()
    console.print(table)

    # Summary
    if total_wasted_space >= 1024**3:
        total_wasted_str = f"{total_wasted_space / 1024**3:.2f} GB"
    elif total_wasted_space >= 1024**2:
        total_wasted_str = f"{total_wasted_space / 1024**2:.2f} MB"
    else:
        total_wasted_str = f"{total_wasted_space / 1024:.2f} KB"

    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Duplicate files: [bold]{total_duplicates}[/bold]")
    console.print(f"  Wasted space: [bold]{total_wasted_str}[/bold]")
    console.print()

    if not apply:
        console.print("[info]Dry run: No files deleted[/info]")
        console.print("[info]Run with --apply to delete duplicates (keeps first file in each group)[/info]")
        return

    # Delete duplicates (keep first file in each group)
    deleted_count = 0
    error_count = 0

    console.print("[warning]Deleting duplicates (keeping first file in each group)...[/warning]")
    console.print()

    for file_group in duplicates.values():
        # Keep the first file, delete the rest
        for file_path in sorted(file_group)[1:]:
            try:
                file_path.unlink()
                deleted_count += 1
                rel_path = file_path.relative_to(target) if target.is_dir() else file_path.name
                console.print(f"  [success]✓[/success] Deleted {rel_path}")
            except Exception as e:
                error_count += 1
                console.print(f"  [error]✗ Error deleting {file_path.name}: {e}[/error]")

    console.print()
    if error_count > 0:
        console.print(f"[warning]Deleted {deleted_count} files, {error_count} errors[/warning]")
    else:
        console.print(f"[success]Successfully deleted {deleted_count} duplicate files[/success]")


def _find_fuzzy_duplicates(path: Path, apply: bool, recursive: bool):
    """Find potential duplicates using metadata matching."""
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))

    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    console.print(f"\n[info]Scanning {len(files)} files for fuzzy duplicates...[/info]")

    # Read metadata for all files
    file_metadata = []

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Reading metadata...", total=len(files))

            for audio_path in files:
                progress.advance(task)
                info = read_audio(audio_path)
                if not info.error:
                    file_metadata.append((audio_path, info))

    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    # Group by metadata similarity
    # Use (artist, album, title) as key, allowing for slight duration differences
    metadata_groups = defaultdict(list)

    for audio_path, info in file_metadata:
        # Extract common tags (normalize to lowercase for comparison)
        artist = ""
        title = ""
        album = ""

        for key, value in info.tags.items():
            key_lower = key.lower()
            if "artist" in key_lower and not "album" in key_lower:
                artist = value.lower().strip()
            elif "title" in key_lower:
                title = value.lower().strip()
            elif "album" in key_lower:
                album = value.lower().strip()

        # Create a fuzzy key (artist + title is usually enough)
        if artist and title:
            fuzzy_key = (artist, title, round(info.duration))
            metadata_groups[fuzzy_key].append((audio_path, info))

    # Filter to groups with multiple files
    potential_duplicates = {k: v for k, v in metadata_groups.items() if len(v) > 1}

    if not potential_duplicates:
        console.print("\n[info]No fuzzy duplicates found[/info]")
        return

    # Display results
    console.print()
    console.print(f"[bold]Found {len(potential_duplicates)} groups of potential duplicates:[/bold]")
    console.print()

    for i, ((artist, title, duration), file_group) in enumerate(sorted(potential_duplicates.items()), 1):
        console.print(f"[bold cyan]Group {i}:[/bold cyan] {artist} - {title} (~{duration}s)")

        for j, (file_path, info) in enumerate(sorted(file_group, key=lambda x: x[1].sample_rate, reverse=True), 1):
            rel_path = file_path.relative_to(target) if target.is_dir() else file_path.name
            quality = f"{info.format} {info.sample_rate_str}"
            if info.bit_depth:
                quality += f" {info.bit_depth}-bit"

            marker = "[dim](highest quality)[/dim]" if j == 1 else "[warning](duplicate)[/warning]"
            console.print(f"  {j}. {rel_path}")
            console.print(f"      {quality} {marker}")

        console.print()

    total_duplicates = sum(len(group) - 1 for group in potential_duplicates.values())
    console.print(f"[bold]Total potential duplicates: {total_duplicates}[/bold]")
    console.print()

    if not apply:
        console.print("[info]Dry run: No files deleted[/info]")
        console.print("[warning]WARNING: Fuzzy matching may have false positives![/warning]")
        console.print("[info]Review carefully before using --apply[/info]")
        return

    console.print("[error]--apply is not supported for fuzzy duplicates[/error]")
    console.print("[error]Please review results and delete manually to avoid data loss[/error]")
    raise typer.Exit(1)
