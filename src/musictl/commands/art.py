"""Album art management commands."""

from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from musictl.core.artwork import (
    read_artwork,
    embed_artwork,
    extract_artwork_data,
    remove_artwork,
    detect_image_format,
)
from musictl.core.scanner import walk_audio_files
from musictl.utils.console import console, format_size

app = typer.Typer(help="Album art operations")


@app.command()
def show(
    path: Path = typer.Argument(..., help="Audio file or directory"),
    summary: bool = typer.Option(False, "--summary", "-s", help="Only show counts, no per-file details"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Display album art information for audio files."""
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))
    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    has_art_count = 0
    no_art_count = 0

    for audio_path in files:
        artworks = read_artwork(audio_path)

        if not artworks:
            no_art_count += 1
            if not summary:
                rel_path = audio_path.relative_to(target) if target.is_dir() else audio_path.name
                console.print(f"[path]{rel_path}[/path]: [warning]No artwork[/warning]")
            continue

        has_art_count += 1
        if not summary:
            rel_path = audio_path.relative_to(target) if target.is_dir() else audio_path.name
            console.print(f"\n[info]{rel_path}[/info]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Type")
            table.add_column("MIME")
            table.add_column("Size")
            table.add_column("Dimensions")

            for art in artworks:
                dims = f"{art.width}x{art.height}" if art.width and art.height else "—"
                table.add_row(
                    art.picture_type,
                    art.mime_type,
                    format_size(art.size_bytes),
                    dims,
                )

            console.print(table)

    console.print()
    total = has_art_count + no_art_count
    console.print(f"[info]{has_art_count} files with artwork, {no_art_count} without ({total} total)[/info]")


@app.command()
def embed(
    path: Path = typer.Argument(..., help="Audio file or directory"),
    image: Path = typer.Option(..., "--image", "-i", help="Image file to embed"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace existing artwork"),
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default is dry-run)"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Embed album art into audio files.

    Examples:
        musictl art embed ~/Music/Album/ --image cover.jpg --apply
    """
    target = Path(path).expanduser().resolve()
    image_path = Path(image).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    if not image_path.exists() or not image_path.is_file():
        console.print(f"[error]Image not found: {image_path}[/error]")
        raise typer.Exit(1)

    # Read and validate image
    image_data = image_path.read_bytes()
    mime_type, _ = detect_image_format(image_data)
    if mime_type == "application/octet-stream":
        console.print("[error]Unrecognized image format (expected JPEG or PNG)[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))
    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    console.print(f"[info]Image: {image_path.name} ({mime_type}, {format_size(len(image_data))})[/info]")

    embedded_count = 0
    skipped_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Embedding artwork...", total=len(files))

        for audio_path in files:
            progress.advance(task)
            rel_path = audio_path.relative_to(target) if target.is_dir() else audio_path.name

            existing = read_artwork(audio_path)
            if existing and not overwrite:
                skipped_count += 1
                continue

            if apply:
                success = embed_artwork(audio_path, image_data, mime_type, overwrite=overwrite)
                if success:
                    embedded_count += 1
                    progress.console.print(f"  [success]✓[/success] Embedded: {rel_path}")
                else:
                    progress.console.print(f"  [error]✗[/error] Failed: {rel_path}")
            else:
                embedded_count += 1
                action = "Would replace" if existing else "Would embed"
                progress.console.print(f"  [info]{action}:[/info] {rel_path}")

    console.print()
    if apply:
        console.print(f"[success]Embedded artwork in {embedded_count} files[/success]")
        if skipped_count > 0:
            console.print(f"[warning]Skipped {skipped_count} files (use --overwrite to replace)[/warning]")
    else:
        console.print(f"[info]Dry run: {embedded_count} files would be updated[/info]")
        if skipped_count > 0:
            console.print(f"[warning]{skipped_count} files already have artwork (use --overwrite)[/warning]")
        if embedded_count > 0:
            console.print("[info]Run with --apply to save changes[/info]")


@app.command()
def extract(
    path: Path = typer.Argument(..., help="Audio file or directory"),
    dest: Path = typer.Option(None, "--dest", "-d", help="Destination directory (default: same as audio)"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing image files"),
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default is dry-run)"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Extract album art from audio files.

    Extracts one cover image per directory (albums typically share artwork).

    Examples:
        musictl art extract ~/Music/Album/ --apply
        musictl art extract ~/Music/ --dest ~/covers/ --apply
    """
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))
    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    extracted_count = 0
    skipped_count = 0
    no_art_count = 0
    seen_dirs: set[Path] = set()

    for audio_path in files:
        # Only extract once per directory
        audio_dir = audio_path.parent
        if audio_dir in seen_dirs:
            continue

        art_data = extract_artwork_data(audio_path)
        if not art_data:
            no_art_count += 1
            continue

        seen_dirs.add(audio_dir)
        image_bytes, mime_type = art_data

        # Determine output path
        if dest:
            dest_dir = Path(dest).expanduser().resolve()
        else:
            dest_dir = audio_dir

        ext = ".jpg" if "jpeg" in mime_type else ".png"
        output_path = dest_dir / f"cover{ext}"

        rel_path = audio_path.relative_to(target) if target.is_dir() else audio_path.name

        if output_path.exists() and not overwrite:
            skipped_count += 1
            console.print(f"  [warning]Exists (skip):[/warning] {output_path.name} in {audio_dir.name}/")
            continue

        if apply:
            dest_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            extracted_count += 1
            console.print(f"  [success]✓[/success] Extracted: {rel_path} → {output_path.name}")
        else:
            extracted_count += 1
            console.print(f"  [info]Would extract:[/info] {rel_path} → {output_path.name}")

    console.print()
    if apply:
        console.print(f"[success]Extracted artwork from {extracted_count} directories[/success]")
    else:
        console.print(f"[info]Dry run: {extracted_count} directories would have artwork extracted[/info]")
        if skipped_count > 0:
            console.print(f"[warning]{skipped_count} already exist (use --overwrite)[/warning]")
        if extracted_count > 0:
            console.print("[info]Run with --apply to extract artwork[/info]")


@app.command()
def remove(
    path: Path = typer.Argument(..., help="Audio file or directory"),
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default is dry-run)"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
):
    """Remove album art from audio files.

    Examples:
        musictl art remove ~/Music/Album/ --apply
    """
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))
    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    removed_count = 0
    skipped_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Removing artwork...", total=len(files))

        for audio_path in files:
            progress.advance(task)

            artworks = read_artwork(audio_path)
            if not artworks:
                skipped_count += 1
                continue

            rel_path = audio_path.relative_to(target) if target.is_dir() else audio_path.name

            if apply:
                success = remove_artwork(audio_path)
                if success:
                    removed_count += 1
                    progress.console.print(f"  [success]✓[/success] Removed: {rel_path}")
                else:
                    progress.console.print(f"  [error]✗[/error] Failed: {rel_path}")
            else:
                removed_count += 1
                art = artworks[0]
                progress.console.print(
                    f"  [info]Would remove:[/info] {rel_path} ({art.mime_type}, {format_size(art.size_bytes)})"
                )

    console.print()
    if apply:
        console.print(f"[success]Removed artwork from {removed_count} files[/success]")
        if skipped_count > 0:
            console.print(f"[info]{skipped_count} files had no artwork[/info]")
    else:
        console.print(f"[info]Dry run: {removed_count} files would have artwork removed[/info]")
        if skipped_count > 0:
            console.print(f"[info]{skipped_count} files have no artwork[/info]")
        if removed_count > 0:
            console.print("[info]Run with --apply to remove artwork[/info]")
