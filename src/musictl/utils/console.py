"""Rich console setup and shared output helpers."""

from rich.console import Console
from rich.table import Table
from rich.theme import Theme

custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "tag_key": "bold cyan",
        "tag_value": "white",
        "path": "dim",
    }
)

console = Console(theme=custom_theme)
err_console = Console(stderr=True, theme=custom_theme)


def make_tag_table(title: str = "Tags") -> Table:
    """Create a consistently styled table for displaying audio tags."""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Tag", style="tag_key", min_width=20)
    table.add_column("Value", style="tag_value")
    return table


def make_file_table(title: str = "Files") -> Table:
    """Create a consistently styled table for displaying file listings."""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("File", style="path")
    table.add_column("Format", justify="center")
    table.add_column("Sample Rate", justify="right")
    table.add_column("Bit Depth", justify="right")
    table.add_column("Duration", justify="right")
    return table
