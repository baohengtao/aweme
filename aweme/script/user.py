import select
import sys
import time
from itertools import islice
from pathlib import Path

import pendulum
from peewee import fn
from typer import Option, Typer

from aweme import console
from aweme.model import UserConfig
from aweme.page import Page

from .helper import LogSaver, default_path, logsaver_decorator, print_command

app = Typer()


@app.command()
@logsaver_decorator
def user_add(max_user: int = 20,
             all_user: bool = Option(False, '--all-user', '-a')):
    if all_user:
        max_user = None
    page = Page.get_self_page()
    uids = {u.user_id for u in UserConfig.select().where(UserConfig.following)}
    uids_following = [int(u['uid']) for u
                      in islice(page.get_following(), max_user)]
    to_add = [uid for uid in uids_following if uid not in uids]
    if max_user is None:
        if uids := uids - set(uids_following):
            raise ValueError(f'there are uids {uids} not in following list')
    console.log(f'{len(to_add)} users will be added')
    for u in to_add[::-1]:
        console.log(f'adding {u} to UserConfig...')
        console.log(UserConfig.from_id(u), '\n')


@app.command()
@logsaver_decorator
def user_loop(frequency: float = 2,
              download_dir: Path = default_path,
              ):

    WORKING_TIME = 20
    logsaver = LogSaver('user_loop', download_dir)
    while True:
        print_command()
        post_count = ((time.time()-UserConfig.aweme_fetch_at.to_timestamp())
                      / UserConfig.post_cycle).desc()
        start_time = pendulum.now()
        query = (UserConfig.select()
                 .where(UserConfig.aweme_fetch
                        | UserConfig.aweme_fetch.is_null(True))
                 .order_by(post_count, UserConfig.id))
        if configs := (query
                       .where(UserConfig.aweme_fetch_at.is_null(True)
                              & UserConfig.aweme_cache_at.is_null(True))
                       .order_by(UserConfig.aweme_fetch.desc(nulls='last'),
                                 UserConfig.id)):
            console.log(
                f'total {configs.count()} new users found, fetching...')
        elif configs := query.where(UserConfig.aweme_next_fetch < pendulum.now()):
            console.log(
                f' {len(configs)} users satisfy fetching conditions, '
                'Fetching 5 users whose estimated new posts is most.')
            configs = configs[:5]
        else:
            configs = (query.limit(2).order_by(fn.COALESCE(
                UserConfig.aweme_fetch_at,
                UserConfig.aweme_cache_at)))
            console.log(
                'no user satisfy fetching conditions, '
                'fetching 2 users whose fetch/cache at is earliest.')
        for i, config in enumerate(configs):
            if start_time.diff().in_minutes() > WORKING_TIME:
                break
            console.log(f'fetching {i+1}/{len(configs)}: {config.username}')
            config = UserConfig.from_id(user_id=config.user_id)
            is_new = (config.aweme_fetch_at is None and config.aweme_fetch)
            config.fetch_aweme(download_dir)
            if is_new:
                logsaver.save_log(save_manually=True)
                print_command()

        console.log(
            f'have been working for {start_time.diff().in_minutes()}m '
            f'which is more than {WORKING_TIME}m, taking a break')

        logsaver.save_log()
        next_start_time = pendulum.now().add(hours=frequency)
        console.rule(f'waiting for next fetching at {next_start_time:%H:%M:%S}',
                     style='magenta on dark_magenta')
        console.log(
            "Press S to fetching immediately,\n"
            "L to save log,\n"
            "Q to exit,\n",
            style='info'
        )
        while pendulum.now() < next_start_time:
            # sleeping for  600 seconds while listing for enter key
            if select.select([sys.stdin], [], [], 600)[0]:
                match (input().lower()):
                    case "s":
                        console.log(
                            "S pressed. continuing immediately.")
                        break
                    case "q":
                        console.log("Q pressed. exiting.")
                        return
                    case "l":
                        logsaver.save_log(save_manually=True)
                    case _:
                        console.log(
                            "Press S to fetching immediately,\n"
                            "L to save log,\n"
                            "Q to exit,\n"
                        )


@app.command()
def write_meta(download_dir: Path = default_path):
    from imgmeta.script import rename, write_meta
    for folder in ['User', 'New']:
        ori = download_dir / folder
        if ori.exists():
            write_meta(ori)
            rename(ori, new_dir=True, root=ori.parent / (ori.stem + 'Pro'))
