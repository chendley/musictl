"""Library scanning and reporting commands."""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import mutagen
import typer
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table

from musictl.core.audio import read_audio
from musictl.core.encoding import detect_non_utf8_tags, guess_encoding
from musictl.core.hasher import file_hash, quick_hash
from musictl.core.scanner import walk_audio_files
from musictl.utils.console import console, format_size, make_file_table

app = typer.Typer(help="Library scanning and reporting")


@app.command(name="library")
def scan_library(
    path: Path = typer.Argument(..., help="Directory to scan"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
    export: Path = typer.Option(None, "--export", "-e", help="Export results to file"),
    export_format: str = typer.Option("csv", "--format", "-f", help="Export format: csv or json"),
):
    """Full library scan with comprehensive statistics."""
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    if export and export_format not in ("csv", "json"):
        console.print(f"[error]Invalid format: {export_format}. Use 'csv' or 'json'[/error]")
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

        format_table.add_row(
            fmt,
            str(count),
            duration_str,
            format_size(size),
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

    console.print(f"[bold cyan]Summary:[/bold cyan]")
    console.print(f"  Total files: [bold]{len(files)}[/bold]")
    console.print(f"  Total duration: [bold]{total_duration_str}[/bold]")
    console.print(f"  Total size: [bold]{format_size(total_size)}[/bold]")

    if id3v1_count > 0:
        console.print(f"  [warning]Files with ID3v1 tags: {id3v1_count}[/warning]")

    if errors_count > 0:
        console.print(f"  [error]Files with errors: {errors_count}[/error]")

    # Export if requested
    if export:
        export_path = Path(export).expanduser().resolve()
        try:
            if export_format == "json":
                # Build JSON structure
                data = {
                    "scan_path": str(target),
                    "total_files": len(files),
                    "total_duration_seconds": total_duration,
                    "total_size_bytes": total_size,
                    "errors": errors_count,
                    "id3v1_count": id3v1_count,
                    "formats": [
                        {
                            "format": fmt,
                            "count": format_counts[fmt],
                            "duration_seconds": format_durations[fmt],
                            "size_bytes": format_sizes[fmt],
                            "percentage": (format_counts[fmt] / len(files)) * 100
                        }
                        for fmt in sorted(format_counts.keys())
                    ],
                    "sample_rates": [
                        {
                            "sample_rate_hz": sr,
                            "count": sample_rate_counts[sr],
                            "percentage": (sample_rate_counts[sr] / len(files)) * 100
                        }
                        for sr in sorted([s for s in sample_rate_counts.keys() if s > 0], reverse=True)
                    ],
                    "bit_depths": [
                        {
                            "bit_depth": bd,
                            "count": bit_depth_counts[bd],
                            "percentage": (bit_depth_counts[bd] / len(files)) * 100
                        }
                        for bd in sorted([b for b in bit_depth_counts.keys() if b > 0], reverse=True)
                    ]
                }
                with open(export_path, "w") as f:
                    json.dump(data, f, indent=2)
            else:  # CSV
                with open(export_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    # Summary section
                    writer.writerow(["Library Statistics"])
                    writer.writerow(["Scan Path", str(target)])
                    writer.writerow(["Total Files", len(files)])
                    writer.writerow(["Total Duration (seconds)", total_duration])
                    writer.writerow(["Total Size (bytes)", total_size])
                    writer.writerow(["Errors", errors_count])
                    writer.writerow(["ID3v1 Count", id3v1_count])
                    writer.writerow([])
                    # Format distribution
                    writer.writerow(["Format Distribution"])
                    writer.writerow(["Format", "Count", "Duration (seconds)", "Size (bytes)", "Percentage"])
                    for fmt in sorted(format_counts.keys()):
                        writer.writerow([
                            fmt,
                            format_counts[fmt],
                            format_durations[fmt],
                            format_sizes[fmt],
                            (format_counts[fmt] / len(files)) * 100
                        ])
                    writer.writerow([])
                    # Sample rate distribution
                    writer.writerow(["Sample Rate Distribution"])
                    writer.writerow(["Sample Rate (Hz)", "Count", "Percentage"])
                    for sr in sorted([s for s in sample_rate_counts.keys() if s > 0], reverse=True):
                        writer.writerow([sr, sample_rate_counts[sr], (sample_rate_counts[sr] / len(files)) * 100])
                    writer.writerow([])
                    # Bit depth distribution
                    if any(bd > 0 for bd in bit_depth_counts.keys()):
                        writer.writerow(["Bit Depth Distribution"])
                        writer.writerow(["Bit Depth", "Count", "Percentage"])
                        for bd in sorted([b for b in bit_depth_counts.keys() if b > 0], reverse=True):
                            writer.writerow([bd, bit_depth_counts[bd], (bit_depth_counts[bd] / len(files)) * 100])

            console.print(f"\n[success]Exported to: {export_path}[/success]")
        except Exception as e:
            console.print(f"\n[error]Export failed: {e}[/error]")

    console.print()


@app.command()
def encoding(
    path: Path = typer.Argument(..., help="Directory to scan"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
    export: Path = typer.Option(None, "--export", "-e", help="Export results to file"),
    export_format: str = typer.Option("csv", "--format", "-f", help="Export format: csv or json"),
):
    """Scan for files with non-UTF-8 encoded tags."""
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    files = [f for f in walk_audio_files(target, recursive=recursive) if f.suffix.lower() == ".mp3"]

    if not files:
        console.print("[warning]No MP3 files found[/warning]")
        raise typer.Exit(0)

    if export and export_format not in ("csv", "json"):
        console.print(f"[error]Invalid format: {export_format}. Use 'csv' or 'json'[/error]")
        raise typer.Exit(1)

    found_count = 0
    suspect_files = []  # Store for export

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

                file_info = {"path": str(rel_path), "tags": {}}
                for key, raw_bytes in suspect.items():
                    guesses = guess_encoding(raw_bytes)
                    progress.console.print(f"  [tag_key]{key}[/tag_key]:")
                    tag_guesses = []
                    for enc, desc, decoded in guesses[:3]:
                        progress.console.print(f"    [{enc}] {decoded}")
                        tag_guesses.append({"encoding": enc, "description": desc, "text": decoded})
                    file_info["tags"][key] = tag_guesses
                suspect_files.append(file_info)
    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    console.print(f"\n[info]Found {found_count} files with suspect encoding out of {len(files)} MP3s[/info]")

    # Export if requested
    if export and suspect_files:
        export_path = Path(export).expanduser().resolve()
        try:
            if export_format == "json":
                data = {
                    "scan_path": str(target),
                    "total_scanned": len(files),
                    "suspect_count": found_count,
                    "files": suspect_files
                }
                with open(export_path, "w") as f:
                    json.dump(data, f, indent=2)
            else:  # CSV
                with open(export_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["File Path", "Tag", "Possible Encoding", "Description", "Decoded Text"])
                    for file_info in suspect_files:
                        for tag, guesses in file_info["tags"].items():
                            for guess in guesses:
                                writer.writerow([
                                    file_info["path"],
                                    tag,
                                    guess["encoding"],
                                    guess["description"],
                                    guess["text"]
                                ])

            console.print(f"[success]Exported to: {export_path}[/success]")
        except Exception as e:
            console.print(f"[error]Export failed: {e}[/error]")


@app.command()
def missing(
    path: Path = typer.Argument(..., help="Directory to scan"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
    export: Path = typer.Option(None, "--export", "-e", help="Export results to file"),
    export_format: str = typer.Option("csv", "--format", "-f", help="Export format: csv or json"),
):
    """Find files with missing or incomplete metadata (artist, album, title, year)."""
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))

    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    if export and export_format not in ("csv", "json"):
        console.print(f"[error]Invalid format: {export_format}. Use 'csv' or 'json'[/error]")
        raise typer.Exit(1)

    # Required tags to check for
    required_tags = ["artist", "album", "title", "date"]  # 'date' covers year/TDRC
    missing_files = []

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning for missing tags...", total=len(files))

            for audio_path in files:
                progress.advance(task)
                info = read_audio(audio_path)

                if info.error:
                    continue

                # Check which required tags are missing
                missing = []
                tags_lower = {k.lower(): v for k, v in info.tags.items()}

                # Check artist (TPE1, artist, albumartist)
                if not any(k in tags_lower for k in ["artist", "albumartist", "tpe1"]):
                    missing.append("artist")

                # Check album (TALB, album)
                if not any(k in tags_lower for k in ["album", "talb"]):
                    missing.append("album")

                # Check title (TIT2, title)
                if not any(k in tags_lower for k in ["title", "tit2"]):
                    missing.append("title")

                # Check date/year (TDRC, date, year)
                if not any(k in tags_lower for k in ["date", "year", "tdrc"]):
                    missing.append("year")

                if missing:
                    missing_files.append({
                        "path": audio_path,
                        "missing": missing,
                        "format": info.format
                    })

    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    if not missing_files:
        console.print("\n[success]All files have complete metadata![/success]")
        return

    # Display results
    console.print()
    console.print(f"[bold]Files with Missing Tags:[/bold]")
    console.print()

    for file_info in missing_files:
        rel_path = file_info["path"].relative_to(target) if target.is_dir() else file_info["path"].name
        missing_str = ", ".join(file_info["missing"])
        console.print(f"  [warning]{rel_path}[/warning]")
        console.print(f"    Missing: [error]{missing_str}[/error]")

    console.print()
    console.print(f"[info]Found {len(missing_files)} files with incomplete metadata out of {len(files)} total[/info]")

    # Export if requested
    if export:
        export_path = Path(export).expanduser().resolve()
        try:
            if export_format == "json":
                data = {
                    "scan_path": str(target),
                    "total_scanned": len(files),
                    "incomplete_count": len(missing_files),
                    "files": [
                        {
                            "path": str(f["path"].relative_to(target)),
                            "format": f["format"],
                            "missing_tags": f["missing"]
                        }
                        for f in missing_files
                    ]
                }
                with open(export_path, "w") as f:
                    json.dump(data, f, indent=2)
            else:  # CSV
                with open(export_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["File Path", "Format", "Missing Tags"])
                    for file_info in missing_files:
                        writer.writerow([
                            str(file_info["path"].relative_to(target)),
                            file_info["format"],
                            ", ".join(file_info["missing"])
                        ])

            console.print(f"[success]Exported to: {export_path}[/success]")
        except Exception as e:
            console.print(f"[error]Export failed: {e}[/error]")


@app.command()
def hires(
    path: Path = typer.Argument(..., help="Directory to scan"),
    threshold: int = typer.Option(48000, "--threshold", "-t", help="Sample rate threshold in Hz"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
    export: Path = typer.Option(None, "--export", "-e", help="Export results to file"),
    export_format: str = typer.Option("csv", "--format", "-f", help="Export format: csv or json"),
):
    """Find hi-res audio files (sample rate above threshold)."""
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))

    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    if export and export_format not in ("csv", "json"):
        console.print(f"[error]Invalid format: {export_format}. Use 'csv' or 'json'[/error]")
        raise typer.Exit(1)

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

    # Export if requested
    if export and hires_files:
        export_path = Path(export).expanduser().resolve()
        try:
            if export_format == "json":
                data = {
                    "scan_path": str(target),
                    "threshold_hz": threshold,
                    "total_scanned": len(files),
                    "hires_count": len(hires_files),
                    "files": [
                        {
                            "path": str(info.path.relative_to(target)),
                            "format": info.format,
                            "sample_rate_hz": info.sample_rate,
                            "bit_depth": info.bit_depth,
                            "duration_seconds": info.duration,
                            "channels": info.channels
                        }
                        for info in sorted(hires_files, key=lambda i: i.sample_rate, reverse=True)
                    ]
                }
                with open(export_path, "w") as f:
                    json.dump(data, f, indent=2)
            else:  # CSV
                with open(export_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["File Path", "Format", "Sample Rate (Hz)", "Bit Depth", "Duration (seconds)", "Channels"])
                    for info in sorted(hires_files, key=lambda i: i.sample_rate, reverse=True):
                        writer.writerow([
                            str(info.path.relative_to(target)),
                            info.format,
                            info.sample_rate,
                            info.bit_depth if info.bit_depth else "",
                            info.duration,
                            info.channels
                        ])

            console.print(f"[success]Exported to: {export_path}[/success]")
        except Exception as e:
            console.print(f"[error]Export failed: {e}[/error]")


def _get_easy_tag(mfile: Any, key: str) -> str | None:
    """Get a single tag value from a mutagen easy file, or None."""
    if mfile is None or mfile.tags is None:
        return None
    vals = mfile.tags.get(key)
    if vals and vals[0]:
        return vals[0]
    return None


@app.command()
def consistency(
    path: Path = typer.Argument(..., help="Directory to scan"),
    summary: bool = typer.Option(False, "--summary", "-s", help="Only show counts"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Check album consistency (mismatched tags, track numbering issues).

    Groups files by directory and checks for inconsistencies within each album.

    Examples:
        musictl scan consistency ~/Music
        musictl scan consistency ~/Music --summary
    """
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))
    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    # Group files by directory
    dirs: dict[Path, list[Path]] = defaultdict(list)
    for f in files:
        dirs[f.parent].append(f)

    albums_checked = 0
    albums_with_issues = 0

    for album_dir in sorted(dirs):
        audio_files = dirs[album_dir]
        if len(audio_files) < 2:
            albums_checked += 1
            continue

        # Read tags for all files in this directory
        file_tags: list[tuple[Path, dict[str, str | None]]] = []
        for audio_path in audio_files:
            try:
                mfile = mutagen.File(str(audio_path), easy=True)
            except Exception:
                continue

            tags = {
                "title": _get_easy_tag(mfile, "title"),
                "artist": _get_easy_tag(mfile, "artist"),
                "album": _get_easy_tag(mfile, "album"),
                "albumartist": _get_easy_tag(mfile, "albumartist"),
                "tracknumber": _get_easy_tag(mfile, "tracknumber"),
            }
            file_tags.append((audio_path, tags))

        if not file_tags:
            continue

        albums_checked += 1
        issues: list[str] = []

        # 1. Mismatched album name
        album_names = {t["album"] for _, t in file_tags if t["album"]}
        if len(album_names) > 1:
            issues.append(f"Mismatched album: {', '.join(repr(a) for a in sorted(album_names))}")

        # 2. Mismatched album artist
        has_albumartist = any(t["albumartist"] for _, t in file_tags)
        if has_albumartist:
            aa_set = {t["albumartist"] for _, t in file_tags if t["albumartist"]}
            if len(aa_set) > 1:
                issues.append(f"Mismatched album artist: {', '.join(repr(a) for a in sorted(aa_set))}")

        # 3-5. Track number checks
        track_numbers: list[tuple[Path, int]] = []
        missing_track = 0
        for fpath, t in file_tags:
            raw = t["tracknumber"]
            if not raw:
                missing_track += 1
                continue
            # Handle "3/12" format
            num_str = raw.split("/")[0].strip()
            try:
                track_numbers.append((fpath, int(num_str)))
            except ValueError:
                missing_track += 1

        if missing_track > 0:
            issues.append(f"Missing track number: {missing_track} files")

        if track_numbers:
            nums = [n for _, n in track_numbers]
            # Duplicate track numbers
            num_counts = Counter(nums)
            dupes = {n: c for n, c in num_counts.items() if c > 1}
            if dupes:
                dupe_strs = [f"#{n} ({c}x)" for n, c in sorted(dupes.items())]
                issues.append(f"Duplicate tracks: {', '.join(dupe_strs)}")

            # Gaps in numbering
            if len(nums) >= 2:
                expected = set(range(min(nums), max(nums) + 1))
                gaps = sorted(expected - set(nums))
                if gaps and len(gaps) <= 5:
                    issues.append(f"Track gaps: missing {', '.join(str(g) for g in gaps)}")
                elif gaps:
                    issues.append(f"Track gaps: {len(gaps)} missing numbers")

        # 6. Missing essential tags
        missing_essential = 0
        for _, t in file_tags:
            if not t["title"] or not t["artist"] or not t["album"]:
                missing_essential += 1
        if missing_essential > 0:
            issues.append(f"Missing essential tags: {missing_essential} files")

        if issues:
            albums_with_issues += 1
            if not summary:
                rel_dir = album_dir.relative_to(target) if target.is_dir() else album_dir.name
                console.print(f"\n[warning]{rel_dir}/[/warning] ({len(file_tags)} files)")
                for issue in issues:
                    console.print(f"  [error]•[/error] {issue}")

    console.print()
    console.print(f"[info]{albums_checked} albums checked, {albums_with_issues} with issues[/info]")


@app.command()
def dupes(
    path: Path = typer.Argument(..., help="Directory to scan"),
    fuzzy: bool = typer.Option(False, "--fuzzy", help="Use metadata matching instead of exact hashing"),
    summary: bool = typer.Option(False, "--summary", "-s", help="Only show totals"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
    export: Path = typer.Option(None, "--export", "-e", help="Export results to file"),
    export_format: str = typer.Option("csv", "--format", "-f", help="Export format: csv or json"),
):
    """Scan for duplicate audio files (exact or fuzzy matching).

    Reports duplicate groups without deleting anything.
    Use 'dupes find --apply' if you want to delete duplicates.

    Examples:
        musictl scan dupes ~/Music
        musictl scan dupes ~/Music --fuzzy --summary
        musictl scan dupes ~/Music --export dupes.csv
    """
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    if export and export_format not in ("csv", "json"):
        console.print(f"[error]Invalid format: {export_format}. Use 'csv' or 'json'[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))
    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    if fuzzy:
        duplicates = _scan_fuzzy_dupes(target, files)
    else:
        duplicates = _scan_exact_dupes(target, files)

    if not duplicates:
        console.print("\n[success]No duplicates found![/success]")
        return

    # Calculate stats
    total_groups = len(duplicates)
    total_duplicate_files = sum(len(group["files"]) - 1 for group in duplicates)
    total_wasted = sum(group["wasted_bytes"] for group in duplicates)

    # Display results
    if not summary:
        for group in duplicates:
            console.print(f"\n[bold cyan]Group {group['group']}:[/bold cyan] ", end="")
            if fuzzy:
                console.print(f"{group['key']}")
            else:
                console.print(
                    f"{len(group['files'])} files, "
                    f"{format_size(group['file_size'])} each "
                    f"({format_size(group['wasted_bytes'])} wasted)"
                )
            for entry in group["files"]:
                marker = "[dim](keep)[/dim]" if entry["status"] == "keep" else "[warning](duplicate)[/warning]"
                detail = f" ({entry['quality']})" if "quality" in entry else ""
                console.print(f"  {entry['path']}{detail} {marker}")

    console.print()
    console.print(
        f"[info]{total_groups} duplicate groups, "
        f"{total_duplicate_files} duplicate files, "
        f"{format_size(total_wasted)} wasted[/info]"
    )

    # Export
    if export:
        _export_dupes(export, export_format, target, duplicates, len(files),
                      total_groups, total_duplicate_files, total_wasted)


def _scan_exact_dupes(target: Path, files: list[Path]) -> list[dict]:
    """Find exact duplicates using 2-phase hashing. Returns structured groups."""
    # Phase 1: Quick hash
    quick_groups: dict[str, list[Path]] = defaultdict(list)
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Quick hashing...", total=len(files))
            for audio_path in files:
                progress.advance(task)
                try:
                    qhash = quick_hash(audio_path)
                    quick_groups[qhash].append(audio_path)
                except Exception:
                    pass
    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    potential = [group for group in quick_groups.values() if len(group) > 1]
    if not potential:
        return []

    # Phase 2: Full hash
    full_groups: dict[str, list[Path]] = defaultdict(list)
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            total_to_verify = sum(len(g) for g in potential)
            task = progress.add_task("Verifying...", total=total_to_verify)
            for group in potential:
                for audio_path in group:
                    progress.advance(task)
                    try:
                        fhash = file_hash(audio_path)
                        full_groups[fhash].append(audio_path)
                    except Exception:
                        pass
    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    # Build result structure
    results = []
    group_num = 0
    for hash_val, file_group in sorted(full_groups.items()):
        if len(file_group) < 2:
            continue
        group_num += 1
        file_size = file_group[0].stat().st_size
        sorted_files = sorted(file_group)
        results.append({
            "group": group_num,
            "file_size": file_size,
            "wasted_bytes": file_size * (len(file_group) - 1),
            "files": [
                {
                    "path": str(f.relative_to(target) if target.is_dir() else f.name),
                    "size": file_size,
                    "status": "keep" if i == 0 else "duplicate",
                }
                for i, f in enumerate(sorted_files)
            ],
        })
    return results


def _scan_fuzzy_dupes(target: Path, files: list[Path]) -> list[dict]:
    """Find fuzzy duplicates using metadata. Returns structured groups."""
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

    # Group by (artist, title, duration)
    # Map both Vorbis-style and ID3 frame keys
    _ARTIST_KEYS = {"artist", "tpe1"}
    _TITLE_KEYS = {"title", "tit2"}
    metadata_groups: dict[tuple, list[tuple]] = defaultdict(list)
    for audio_path, info in file_metadata:
        artist = ""
        title = ""
        for key, value in info.tags.items():
            key_lower = key.lower()
            if key_lower in _ARTIST_KEYS:
                artist = value.lower().strip()
            elif key_lower in _TITLE_KEYS:
                title = value.lower().strip()
        if artist and title:
            fuzzy_key = (artist, title, round(info.duration))
            metadata_groups[fuzzy_key].append((audio_path, info))

    # Build result structure
    results = []
    group_num = 0
    for (artist, title, duration), file_group in sorted(metadata_groups.items()):
        if len(file_group) < 2:
            continue
        group_num += 1
        # Sort by sample rate descending (highest quality first)
        sorted_group = sorted(file_group, key=lambda x: x[1].sample_rate, reverse=True)
        total_size = sum(f.stat().st_size for f, _ in sorted_group)
        keep_size = sorted_group[0][0].stat().st_size
        results.append({
            "group": group_num,
            "key": f"{artist} - {title} (~{duration}s)",
            "file_size": keep_size,
            "wasted_bytes": total_size - keep_size,
            "files": [
                {
                    "path": str(f.relative_to(target) if target.is_dir() else f.name),
                    "size": f.stat().st_size,
                    "status": "keep" if i == 0 else "duplicate",
                    "quality": f"{info.format} {info.sample_rate_str}"
                               + (f" {info.bit_depth}-bit" if info.bit_depth else ""),
                }
                for i, (f, info) in enumerate(sorted_group)
            ],
        })
    return results


def _export_dupes(
    export: Path,
    export_format: str,
    target: Path,
    duplicates: list[dict],
    total_files: int,
    total_groups: int,
    total_duplicate_files: int,
    total_wasted: int,
):
    """Export duplicate scan results to CSV or JSON."""
    export_path = Path(export).expanduser().resolve()
    try:
        if export_format == "json":
            data = {
                "scan_path": str(target),
                "total_files": total_files,
                "summary": {
                    "duplicate_groups": total_groups,
                    "duplicate_files": total_duplicate_files,
                    "wasted_bytes": total_wasted,
                },
                "groups": duplicates,
            }
            with open(export_path, "w") as f:
                json.dump(data, f, indent=2)
        else:  # CSV
            with open(export_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Group", "File", "Size", "Status"])
                for group in duplicates:
                    for entry in group["files"]:
                        writer.writerow([
                            group["group"],
                            entry["path"],
                            entry["size"],
                            entry["status"],
                        ])

        console.print(f"\n[success]Exported to: {export_path}[/success]")
    except Exception as e:
        console.print(f"\n[error]Export failed: {e}[/error]")
