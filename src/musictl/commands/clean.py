"""Cleanup operations for junk files."""

from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from musictl.utils.console import console

app = typer.Typer(help="Cleanup operations")


# Patterns for temporary/junk files across all operating systems
TEMP_FILE_PATTERNS = [
    "._*",           # macOS resource forks
    ".DS_Store",     # macOS folder metadata
    "Thumbs.db",     # Windows thumbnail cache
    "desktop.ini",   # Windows folder config
    ".directory",    # KDE/Linux folder metadata
    "*.tmp",         # Generic temporary files
    "*.bak",         # Backup files
    ".AppleDouble",  # macOS AppleDouble files
    ".Spotlight-V100",  # macOS Spotlight
    ".Trashes",      # macOS trash
]


@app.command("temp-files")
def clean_temp_files(
    path: Path = typer.Argument(..., help="Directory to clean"),
    apply: bool = typer.Option(False, "--apply", help="Delete files (default is dry-run)"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Remove OS-generated temporary files (.DS_Store, Thumbs.db, ._ files, etc.)."""
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    console.print(f"\n[info]Scanning for temporary files...[/info]")

    # Find all matching files
    temp_files = []

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning...", total=None)

            for pattern in TEMP_FILE_PATTERNS:
                if recursive:
                    matches = list(target.rglob(pattern))
                else:
                    matches = list(target.glob(pattern))

                temp_files.extend(matches)
                progress.update(task, advance=1)

    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    # Filter to only files (not directories)
    temp_files = [f for f in temp_files if f.is_file()]

    if not temp_files:
        console.print("\n[success]No temporary files found![/success]")
        return

    # Calculate total size
    total_size = sum(f.stat().st_size for f in temp_files)

    if total_size >= 1024**3:
        size_str = f"{total_size / 1024**3:.2f} GB"
    elif total_size >= 1024**2:
        size_str = f"{total_size / 1024**2:.2f} MB"
    elif total_size >= 1024:
        size_str = f"{total_size / 1024:.2f} KB"
    else:
        size_str = f"{total_size} bytes"

    # Display findings
    console.print()
    console.print(f"[bold]Found {len(temp_files)} temporary files:[/bold]")
    console.print()

    # Group by pattern
    by_pattern = {}
    for f in temp_files:
        # Determine which pattern matched
        matched_pattern = None
        for pattern in TEMP_FILE_PATTERNS:
            # Simple pattern matching
            if pattern.startswith("*"):
                # Extension pattern like *.tmp
                if f.name.endswith(pattern[1:]):
                    matched_pattern = pattern
                    break
            elif pattern.endswith("*"):
                # Prefix wildcard pattern like ._*
                if f.name.startswith(pattern[:-1]):
                    matched_pattern = pattern
                    break
            elif f.name == pattern:
                # Exact match like .DS_Store or Thumbs.db
                matched_pattern = pattern
                break

        if matched_pattern:
            if matched_pattern not in by_pattern:
                by_pattern[matched_pattern] = []
            by_pattern[matched_pattern].append(f)

    # Show summary by pattern
    for pattern, files in sorted(by_pattern.items()):
        pattern_size = sum(f.stat().st_size for f in files)
        if pattern_size >= 1024**2:
            pattern_size_str = f"{pattern_size / 1024**2:.2f} MB"
        elif pattern_size >= 1024:
            pattern_size_str = f"{pattern_size / 1024:.2f} KB"
        else:
            pattern_size_str = f"{pattern_size} bytes"

        console.print(f"  [cyan]{pattern}[/cyan]: {len(files)} files ({pattern_size_str})")

    console.print()
    console.print(f"[bold]Total:[/bold] {len(temp_files)} files, {size_str}")
    console.print()

    if not apply:
        console.print("[info]Dry run: No files deleted[/info]")
        console.print("[info]Run with --apply to delete these files[/info]")
        return

    # Delete the files
    deleted_count = 0
    error_count = 0

    console.print("[warning]Deleting temporary files...[/warning]")
    console.print()

    for temp_file in temp_files:
        try:
            temp_file.unlink()
            deleted_count += 1
            rel_path = temp_file.relative_to(target) if target.is_dir() else temp_file.name
            console.print(f"  [success]✓[/success] Deleted {rel_path}")
        except Exception as e:
            error_count += 1
            console.print(f"  [error]✗ Error deleting {temp_file.name}: {e}[/error]")

    console.print()
    if error_count > 0:
        console.print(f"[warning]Deleted {deleted_count} files, {error_count} errors[/warning]")
    else:
        console.print(f"[success]Successfully deleted {deleted_count} temporary files ({size_str} freed)[/success]")
