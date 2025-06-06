
from rich.console import Console
from rich.theme import Theme
from rich.traceback import install

custom_theme = Theme({
    "info": "dim cyan",
    "warning": "bold bright_yellow on dark_goldenrod",
    "error": "bold bright_red on dark_red",
    "notice": "bold magenta"
})
console = Console(theme=custom_theme, record=True, width=126)
install(show_locals=False)
