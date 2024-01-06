from typer import Typer

from aweme import console
from aweme.model import User
from aweme.page import Page

from .helper import logsaver_decorator

app = Typer()


@app.command()
@logsaver_decorator
def user_add():
    page = Page.get_self_page()
    for f in page.get_following():
        console.log(f'fetching {f["homepage"]}')
        console.log(User.from_id(f['uid'], update=True), '\n')
