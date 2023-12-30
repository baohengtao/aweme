from typer import Typer

from . import user

app = Typer()
for app_ in [user.app]:
    app.registered_commands += app_.registered_commands
