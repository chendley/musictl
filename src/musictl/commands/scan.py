"""Library scanning and reporting commands."""

from collections import Counter, defaultdict
from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table

from musictl.core.audio import read_audio
from musictl.core.encoding import detect_non_utf8_tags, guess_encoding
from musictl.core.scanner import walk_audio_files
from musictl.utils.console import console

app = typer.Typer(help="Library scanning and reporting")


@app.command(name="library")
def scan_library(
    path: Path = typer.Argument(..., help="Directory to scan"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Full library scan with comprehensive statistics."""
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))

    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    # Collect statistics
    format_counts = Counter()
    sample_rate_counts = Counter()
    bit_depth_counts = Counter()
    total_duration = 0.0
    total_size = 0
    id3v1_count = 0
    errors_count = 0
    format_durations = defaultdict(float)
    format_sizes = defaultdict(int)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning library...", total=len(files))

            for audio_path in files:
                progress.advance(task)

                # Get file size
                try:
                    file_size = audio_path.stat().st_size
                    total_size += file_size
                except Exception:
                    pass

                # Read audio metadata
                info = read_audio(audio_path)

                if info.error:
                    errors_count += 1
                    continue

                # Count statistics
                format_counts[info.format] += 1
                sample_rate_counts[info.sample_rate] += 1
                bit_depth_counts[info.bit_depth] += 1
                total_duration += info.duration
                format_durations[info.format] += info.duration
                format_sizes[info.format] += file_size

                if info.has_id3v1:
                    id3v1_count += 1

    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    # Display results
    console.print()
    console.print(f"[bold]Library Statistics: {target}[/bold]")
    console.print()

    # Format distribution table
    format_table = Table(title="Format Distribution", show_header=True, header_style="bold magenta")
    format_table.add_column("Format", style="cyan")
    format_table.add_column("Files", justify="right")
    format_table.add_column("Total Duration", justify="right")
    format_table.add_column("Total Size", justify="right")
    format_table.add_column("Percentage", justify="right")

    for fmt in sorted(format_counts.keys()):
        count = format_counts[fmt]
        duration = format_durations[fmt]
        size = format_sizes[fmt]
        percentage = (count / len(files)) * 100

        # Format duration
        hours, remainder = divmod(int(duration), 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m {seconds}s"

        # Format size
        if size >= 1024**3:
            size_str = f"{size / 1024**3:.2f} GB"
        elif size >= 1024**2:
            size_str = f"{size / 1024**2:.2f} MB"
        else:
            size_str = f"{size / 1024:.2f} KB"

        format_table.add_row(
            fmt,
            str(count),
            duration_str,
            size_str,
            f"{percentage:.1f}%"
        )

    console.print(format_table)
    console.print()

    # Sample rate distribution table
    sample_rate_table = Table(title="Sample Rate Distribution", show_header=True, header_style="bold magenta")
    sample_rate_table.add_column("Sample Rate", style="cyan")
    sample_rate_table.add_column("Files", justify="right")
    sample_rate_table.add_column("Percentage", justify="right")

    for sr in sorted([s for s in sample_rate_counts.keys() if s > 0], reverse=True):
        count = sample_rate_counts[sr]
        percentage = (count / len(files)) * 100
        sr_str = f"{sr / 1000:.1f} kHz" if sr >= 1000 else f"{sr} Hz"
        sample_rate_table.add_row(sr_str, str(count), f"{percentage:.1f}%")

    console.print(sample_rate_table)
    console.print()

    # Bit depth distribution table (if available)
    if any(bd > 0 for bd in bit_depth_counts.keys()):
        bit_depth_table = Table(title="Bit Depth Distribution", show_header=True, header_style="bold magenta")
        bit_depth_table.add_column("Bit Depth", style="cyan")
        bit_depth_table.add_column("Files", justify="right")
        bit_depth_table.add_column("Percentage", justify="right")

        for bd in sorted([b for b in bit_depth_counts.keys() if b > 0], reverse=True):
            count = bit_depth_counts[bd]
            percentage = (count / len(files)) * 100
            bit_depth_table.add_row(f"{bd}-bit", str(count), f"{percentage:.1f}%")

        console.print(bit_depth_table)
        console.print()

    # Summary statistics
    hours, remainder = divmod(int(total_duration), 3600)
    minutes, seconds = divmod(remainder, 60)
    total_duration_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"

    if total_size >= 1024**3:
        total_size_str = f"{total_size / 1024**3:.2f} GB"
    elif total_size >= 1024**2:
        total_size_str = f"{total_size / 1024**2:.2f} MB"
    else:
        total_size_str = f"{total_size / 1024:.2f} KB"

    console.print(f"[bold cyan]Summary:[/bold cyan]")
    console.print(f"  Total files: [bold]{len(files)}[/bold]")
    console.print(f"  Total duration: [bold]{total_duration_str}[/bold]")
    console.print(f"  Total size: [bold]{total_size_str}[/bold]")

    if id3v1_count > 0:
        console.print(f"  [warning]Files with ID3v1 tags: {id3v1_count}[/warning]")

    if errors_count > 0:
        console.print(f"  [error]Files with errors: {errors_count}[/error]")

    console.print()


@app.command()
def encoding(
    path: Path = typer.Argument(..., help="Directory to scan"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Scan for files with non-UTF-8 encoded tags."""
    target = Path(path).expanduser().resolve()
    files = [f for f in walk_audio_files(target, recursive=recursive) if f.suffix.lower() == ".mp3"]

    if not files:
        console.print("[warning]No MP3 files found[/warning]")
        raise typer.Exit(0)

    found_count = 0

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning tags...", total=len(files))

            for audio_path in files:
                progress.advance(task)
                suspect = detect_non_utf8_tags(audio_path)
                if not suspect:
                    continue

                found_count += 1
                rel_path = audio_path.relative_to(target)
                progress.console.print(f"\n[warning]Suspect encoding:[/warning] {rel_path}")

                for key, raw_bytes in suspect.items():
                    guesses = guess_encoding(raw_bytes)
                    progress.console.print(f"  [tag_key]{key}[/tag_key]:")
                    for enc, desc, decoded in guesses[:3]:
                        progress.console.print(f"    [{enc}] {decoded}")
    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    console.print(f"\n[info]Found {found_count} files with suspect encoding out of {len(files)} MP3s[/info]")


@app.command()
def hires(
    path: Path = typer.Argument(..., help="Directory to scan"),
    threshold: int = typer.Option(48000, "--threshold", "-t", help="Sample rate threshold in Hz"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Find hi-res audio files (sample rate above threshold)."""
    target = Path(path).expanduser().resolve()
    files = list(walk_audio_files(target, recursive=recursive))

    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    hires_files = []

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning sample rates...", total=len(files))

            for audio_path in files:
                progress.advance(task)
                info = read_audio(audio_path)
                if info.sample_rate > threshold:
                    hires_files.append(info)
    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    if not hires_files:
        console.print(f"[info]No files above {threshold} Hz found[/info]")
        raise typer.Exit(0)

    from musictl.utils.console import make_file_table
    table = make_file_table(title=f"Hi-Res Files (>{threshold} Hz)")
    for info in sorted(hires_files, key=lambda i: i.sample_rate, reverse=True):
        rel_path = info.path.relative_to(target)
        table.add_row(
            str(rel_path),
            info.format,
            info.sample_rate_str,
            f"{info.bit_depth}-bit" if info.bit_depth else "—",
            info.duration_str,
        )

    console.print(table)
    console.print(f"\n[info]Found {len(hires_files)} hi-res files out of {len(files)} total[/info]")
