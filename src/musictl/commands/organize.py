"""File organization commands."""

import shutil
from collections import defaultdict
from pathlib import Path

import typer
from rich.table import Table

from musictl.core.audio import read_audio
from musictl.core.scanner import walk_audio_files
from musictl.utils.console import console

app = typer.Typer(help="File organization operations")


@app.command("by-format")
def organize_by_format(
    path: Path = typer.Argument(..., help="Directory to organize"),
    dest: Path = typer.Option(..., "--dest", "-d", help="Destination directory"),
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default is dry-run)"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Organize files into subdirectories by format (FLAC/, MP3/, etc.)."""
    source = Path(path).expanduser().resolve()
    destination = Path(dest).expanduser().resolve()

    if not source.exists():
        console.print(f"[error]Source path not found: {source}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(source, recursive=recursive))

    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    # Group files by format
    files_by_format = defaultdict(list)

    console.print(f"\n[info]Analyzing {len(files)} files...[/info]")

    for audio_path in files:
        info = read_audio(audio_path)
        if info.error:
            console.print(f"[error]Error reading {audio_path.name}: {info.error}[/error]")
            continue

        files_by_format[info.format].append(audio_path)

    if not files_by_format:
        console.print("[warning]No valid audio files to organize[/warning]")
        raise typer.Exit(0)

    # Display organization plan
    table = Table(title="Organization Plan", show_header=True, header_style="bold magenta")
    table.add_column("Format", style="cyan")
    table.add_column("Files", justify="right")
    table.add_column("Destination", style="dim")

    total_files = 0
    for fmt in sorted(files_by_format.keys()):
        count = len(files_by_format[fmt])
        total_files += count
        dest_dir = destination / fmt
        table.add_row(fmt, str(count), str(dest_dir))

    console.print()
    console.print(table)
    console.print()

    if not apply:
        console.print(f"[info]Dry run: {total_files} files would be organized[/info]")
        console.print("[info]Run with --apply to execute the move[/info]")
        return

    # Execute the move
    moved_count = 0
    error_count = 0

    for fmt, file_list in files_by_format.items():
        dest_dir = destination / fmt
        dest_dir.mkdir(parents=True, exist_ok=True)

        for audio_path in file_list:
            try:
                dest_path = dest_dir / audio_path.name

                # Handle filename conflicts
                if dest_path.exists():
                    # Add a counter to make the filename unique
                    counter = 1
                    stem = audio_path.stem
                    suffix = audio_path.suffix
                    while dest_path.exists():
                        dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                        counter += 1

                shutil.move(str(audio_path), str(dest_path))
                moved_count += 1
                console.print(f"  [success]✓[/success] Moved {audio_path.name} → {fmt}/")

            except Exception as e:
                error_count += 1
                console.print(f"  [error]✗ Error moving {audio_path.name}: {e}[/error]")

    console.print()
    if error_count > 0:
        console.print(f"[warning]Moved {moved_count} files, {error_count} errors[/warning]")
    else:
        console.print(f"[success]Successfully moved {moved_count} files[/success]")


@app.command("by-samplerate")
def organize_by_samplerate(
    path: Path = typer.Argument(..., help="Directory to organize"),
    dest: Path = typer.Option(..., "--dest", "-d", help="Destination directory for hi-res files"),
    threshold: int = typer.Option(48000, "--threshold", "-t", help="Sample rate threshold in Hz"),
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default is dry-run)"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Move hi-res audio files (>threshold sample rate) to destination directory."""
    source = Path(path).expanduser().resolve()
    destination = Path(dest).expanduser().resolve()

    if not source.exists():
        console.print(f"[error]Source path not found: {source}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(source, recursive=recursive))

    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    # Find hi-res files
    hires_files = []
    standard_files = []

    console.print(f"\n[info]Analyzing {len(files)} files...[/info]")

    for audio_path in files:
        info = read_audio(audio_path)
        if info.error:
            console.print(f"[error]Error reading {audio_path.name}: {info.error}[/error]")
            continue

        if info.sample_rate > threshold:
            hires_files.append((audio_path, info))
        else:
            standard_files.append((audio_path, info))

    if not hires_files:
        console.print(f"[info]No files above {threshold} Hz found[/info]")
        raise typer.Exit(0)

    # Display organization plan
    table = Table(title=f"Hi-Res Files (>{threshold} Hz)", show_header=True, header_style="bold magenta")
    table.add_column("File", style="cyan")
    table.add_column("Format", justify="center")
    table.add_column("Sample Rate", justify="right")
    table.add_column("Bit Depth", justify="right")

    for audio_path, info in sorted(hires_files, key=lambda x: x[1].sample_rate, reverse=True):
        rel_path = audio_path.relative_to(source) if source.is_dir() else audio_path.name
        table.add_row(
            str(rel_path),
            info.format,
            info.sample_rate_str,
            f"{info.bit_depth}-bit" if info.bit_depth else "—"
        )

    console.print()
    console.print(table)
    console.print()
    console.print(f"[cyan]Destination:[/cyan] {destination}")
    console.print(f"[cyan]Files to move:[/cyan] {len(hires_files)}")
    console.print(f"[dim]Standard files (remain in place):[/dim] {len(standard_files)}")
    console.print()

    if not apply:
        console.print(f"[info]Dry run: {len(hires_files)} hi-res files would be moved[/info]")
        console.print("[info]Run with --apply to execute the move[/info]")
        return

    # Execute the move
    destination.mkdir(parents=True, exist_ok=True)
    moved_count = 0
    error_count = 0

    for audio_path, info in hires_files:
        try:
            dest_path = destination / audio_path.name

            # Handle filename conflicts
            if dest_path.exists():
                counter = 1
                stem = audio_path.stem
                suffix = audio_path.suffix
                while dest_path.exists():
                    dest_path = destination / f"{stem}_{counter}{suffix}"
                    counter += 1

            shutil.move(str(audio_path), str(dest_path))
            moved_count += 1
            console.print(f"  [success]✓[/success] Moved {audio_path.name} ({info.sample_rate_str})")

        except Exception as e:
            error_count += 1
            console.print(f"  [error]✗ Error moving {audio_path.name}: {e}[/error]")

    console.print()
    if error_count > 0:
        console.print(f"[warning]Moved {moved_count} files, {error_count} errors[/warning]")
    else:
        console.print(f"[success]Successfully moved {moved_count} hi-res files[/success]")
