import sys
from functools import wraps
from inspect import signature
from pathlib import Path

import pendulum
from rich.terminal_theme import MONOKAI

from aweme import console
from aweme.fetcher import fetcher

if not (d := Path('/Volumes/Art')).exists():
    d = Path.home()/'Pictures'
default_path = d / 'Aweme'


def print_command():
    argv = sys.argv
    argv[0] = Path(argv[0]).name
    console.log(
        f" run command  @ {pendulum.now().format('YYYY-MM-DD HH:mm:ss')}")
    console.log(' '.join(argv))


def logsaver_decorator(func):
    """Decorator to save console log to html file"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            with console.capture():
                console.print_exception(show_locals=True)
            raise
        finally:
            callargs = signature(func).bind(*args, **kwargs).arguments
            download_dir = callargs.get('download_dir', default_path)
            save_log(func.__name__, download_dir)

    return wrapper


def save_log(func_name, download_dir: Path):
    download_dir.mkdir(parents=True, exist_ok=True)
    time_format = pendulum.now().format('YY-MM-DD_HHmmss')
    log_file = f"{func_name}_{time_format}.html"
    console.log(f'Saving log to {download_dir / log_file}')
    console.save_html(download_dir / log_file, theme=MONOKAI)


class LogSaver:
    SAVE_LOG_FOR_COUNT = 100
    SAVE_LOG_INTERVAL = 24  # hours

    def __init__(self, command: str, download_dir: Path):
        self.command = command
        self.download_dir = download_dir
        self.save_log_at = pendulum.now()
        self.save_visits_at = fetcher.visits

    def save_log(self, save_manually=False):
        fetch_count = fetcher.visits - self.save_visits_at
        log_hours = self.save_log_at.diff().in_hours()
        console.log(
            f'total fetch count: {fetch_count}, '
            f'threshold: {self.SAVE_LOG_FOR_COUNT}')
        console.log(
            f'log hours: {log_hours}, threshold: {self.SAVE_LOG_INTERVAL}h')
        if (log_hours > self.SAVE_LOG_INTERVAL or
                fetch_count > self.SAVE_LOG_FOR_COUNT):
            console.log('Threshold reached, saving log automatically...')
        elif save_manually:
            console.log('Saving log manually...')
        else:
            return
        save_log(self.command, self.download_dir)
        self.save_log_at = pendulum.now()
        self.save_visits_at = fetcher.visits
