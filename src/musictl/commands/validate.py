"""File validation and integrity checking commands."""

from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table

from musictl.core.audio import read_audio
from musictl.core.scanner import walk_audio_files
from musictl.utils.console import console

app = typer.Typer(help="File validation and integrity checking")


@app.command()
def check(
    path: Path = typer.Argument(..., help="Directory or file to validate"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show details for all files"),
):
    """Validate audio file integrity and detect corrupted files."""
    target = Path(path).expanduser().resolve()

    if not target.exists():
        console.print(f"[error]Path not found: {target}[/error]")
        raise typer.Exit(1)

    files = list(walk_audio_files(target, recursive=recursive))

    if not files:
        console.print("[warning]No audio files found[/warning]")
        raise typer.Exit(0)

    console.print(f"\n[info]Validating {len(files)} files...[/info]")

    valid_files = []
    invalid_files = []
    error_details = []

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Checking file integrity...", total=len(files))

            for audio_path in files:
                progress.advance(task)

                # Try to read the file
                info = read_audio(audio_path)

                if info.error:
                    invalid_files.append(audio_path)
                    error_details.append((audio_path, info.error))

                    if verbose:
                        rel_path = audio_path.relative_to(target) if target.is_dir() else audio_path.name
                        progress.console.print(f"[error]✗[/error] {rel_path}: {info.error}")
                else:
                    valid_files.append(audio_path)

                    if verbose:
                        rel_path = audio_path.relative_to(target) if target.is_dir() else audio_path.name
                        progress.console.print(f"[success]✓[/success] {rel_path}: {info.format} OK")

    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user[/warning]")
        raise typer.Exit(130)

    # Display results
    console.print()

    if invalid_files:
        console.print(f"[bold]Found {len(invalid_files)} corrupted or unreadable files:[/bold]")
        console.print()

        # Show error details in a table
        table = Table(title="Invalid Files", show_header=True, header_style="bold magenta")
        table.add_column("File", style="error")
        table.add_column("Error", style="dim")

        for audio_path, error in error_details:
            rel_path = audio_path.relative_to(target) if target.is_dir() else audio_path.name
            # Truncate long errors
            error_str = error if len(error) < 60 else error[:57] + "..."
            table.add_row(str(rel_path), error_str)

        console.print(table)
        console.print()

    # Summary
    valid_pct = (len(valid_files) / len(files)) * 100 if files else 0

    console.print(f"[bold cyan]Summary:[/bold cyan]")
    console.print(f"  Total files: [bold]{len(files)}[/bold]")
    console.print(f"  Valid files: [success]{len(valid_files)}[/success] ({valid_pct:.1f}%)")

    if invalid_files:
        console.print(f"  Invalid files: [error]{len(invalid_files)}[/error]")
        console.print()
        console.print("[warning]Recommendation: Back up and remove corrupted files[/warning]")
    else:
        console.print()
        console.print("[success]All files validated successfully![/success]")

    console.print()
