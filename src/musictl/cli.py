"""musictl - Music Library Toolkit CLI."""

import typer

from musictl import __version__
from musictl.commands import tags, scan, organize, duplicates, validate, config, clean, art


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        typer.echo(f"musictl version {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="musictl",
    help="A CLI toolkit for managing, fixing, and organizing music libraries.",
    no_args_is_help=True,
)


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    )
):
    """musictl - Music Library Toolkit."""
    pass

app.add_typer(tags.app, name="tags")
app.add_typer(scan.app, name="scan")
app.add_typer(organize.app, name="organize")
app.add_typer(duplicates.app, name="dupes")
app.add_typer(validate.app, name="validate")
app.add_typer(config.app, name="config")
app.add_typer(clean.app, name="clean")
app.add_typer(art.app, name="art")


if __name__ == "__main__":
    app()
