import itertools
import select
import sys
import time
from itertools import islice
from pathlib import Path

import pendulum
from peewee import fn
from rich.prompt import Confirm, Prompt
from typer import Option, Typer

from aweme import console
from aweme.fetcher import fetcher
from aweme.model import Cache, User, UserConfig
from aweme.page import Page

from .helper import LogSaver, default_path, logsaver_decorator, print_command

app = Typer()


@app.command()
@logsaver_decorator
def user_add(max_user: int = 20,
             all_user: bool = Option(False, '--all-user', '-a')):
    fetcher.toggle_alt(False)
    if all_user:
        max_user = None
    page = Page.get_self_page()
    query = UserConfig.select().where(
        UserConfig.following).order_by(UserConfig.id.desc())
    config = query[0]
    console.log(
        f'{query.count()} following users in UserConfig, '
        f'latest user is {config.username} ({config.nickname})')
    uids = {u.user_id for u in query}
    uids_following = [int(u['uid']) for u
                      in islice(page.get_following(), max_user)]
    to_add = [uid for uid in uids_following if uid not in uids]
    if max_user is None:
        console.log(f'{len(uids_following)} user followed')
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

    fetcher.login(alt_login=True)
    fetcher.login(alt_login=False)
    UserConfig.update_table()
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
                'Fetching 10 users whose estimated new posts is most.')
            configs = configs[:10]
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


@app.command(help='Add user to database of users whom we want to fetch from')
@logsaver_decorator
def user(download_dir: Path = default_path):
    """Add user to database of users whom we want to fetch from"""
    fetcher.toggle_alt(False)
    UserConfig.update_table()
    user = UserConfig.select().order_by(UserConfig.id.desc()).first()
    cnt = UserConfig.select().where(UserConfig.following).count()
    console.log(f'total {cnt} users in database')
    console.log(f'the latest added user is {user.username}({user.user_id})')

    while user_id := Prompt.ask('请输入用户名:smile:').strip():
        user_id = user_id.split('?')[0].split('/')[-1].strip()
        if user := (User.get_or_none(username=user_id)
                    or User.get_or_none(sec_uid=user_id)):
            user_id = user.id
        if uc := UserConfig.get_or_none(user_id=user_id):
            console.log(f'用户{uc.username}已在列表中')
        uc = UserConfig.from_id(user_id)
        console.log(uc)
        uc.aweme_fetch = Confirm.ask(f"是否获取{uc.username}的主页？", default=True)
        uc.save()
        console.log(f'用户{uc.username}更新完成')
        if uc.aweme_fetch and not uc.following:
            console.log(f'用户{uc.username}未关注，记得关注🌸', style='notice')
        elif not uc.aweme_fetch and uc.following:
            console.log(f'用户{uc.username}已关注，记得取关🔥', style='notice')
        if not uc.aweme_fetch and Confirm.ask('是否删除该用户？', default=False):
            uc.delete_instance()
            console.log('用户已删除')
        elif uc.aweme_fetch and Confirm.ask('是否现在抓取', default=False):
            uc.fetch_aweme(download_dir)
        console.log()


@app.command()
def clean_database():
    for u in User:
        if (u.artist and u.artist[0].photos_num) or u.config:
            continue
        console.log(u)
        for n in itertools.chain(u.posts, u.artist):
            console.log(n, '\n')

        if Confirm.ask(f'是否删除{u.username}({u.id})？', default=False):
            caches = Cache.select().where(Cache.user_id == u.id)
            assert len(caches) == len(u.posts)
            for n in itertools.chain(u.posts, u.artist, caches):
                n.delete_instance()
            u.delete_instance()
            console.log(f'用户{u.username}已删除')

