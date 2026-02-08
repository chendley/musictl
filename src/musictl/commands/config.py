"""Configuration management commands."""

from pathlib import Path

import typer

from musictl.utils.config import get_config
from musictl.utils.console import console

app = typer.Typer(help="Configuration management")


@app.command()
def init():
    """Create a default config file at ~/.config/musictl/config.toml."""
    config = get_config()

    if config.config_file.exists():
        console.print(f"[warning]Config file already exists:[/warning] {config.config_file}")
        console.print("[info]Edit the file directly or delete it to regenerate[/info]")
        raise typer.Exit(0)

    config.create_example_config()
    console.print(f"[success]Created config file:[/success] {config.config_file}")
    console.print()
    console.print("[info]Edit this file to customize musictl behavior[/info]")


@app.command()
def show():
    """Show the current config file location and contents."""
    config = get_config()

    console.print(f"[bold]Config file location:[/bold] {config.config_file}")
    console.print()

    if not config.config_file.exists():
        console.print("[warning]Config file does not exist[/warning]")
        console.print("[info]Run 'musictl config init' to create one[/info]")
        raise typer.Exit(0)

    console.print("[bold]Current configuration:[/bold]")
    console.print()

    try:
        with open(config.config_file) as f:
            content = f.read()
            console.print(content)
    except Exception as e:
        console.print(f"[error]Error reading config file: {e}[/error]")
        raise typer.Exit(1)


@app.command()
def path():
    """Show the config file path."""
    config = get_config()
    console.print(str(config.config_file))
