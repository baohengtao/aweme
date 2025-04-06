import hashlib
import json
import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlencode

import execjs
import httpx
from bs4 import BeautifulSoup
from exiftool import ExifToolHelper
from furl import furl
from rich.prompt import Confirm
from selenium import webdriver

from aweme import console

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
httpx_logger = logging.getLogger("httpx")
httpx_logger.disabled = True


def _get_session():
    headers = {
        "authority": "www.douyin.com",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120"',
        "accept": "application/json, text/plain, */*",
        "dnt": "1",
        "sec-ch-ua-mobile": "?0",
        "user-agent": UA,
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": "https://www.douyin.com/user",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    }
    cookie_file = Path(__file__).with_name('cookie.json')
    if cookie_file.exists():
        cookies = json.loads(cookie_file.read_text())
    else:
        cookies = {}
    sess_main = httpx.Client(headers=headers, cookies=cookies.get('main'))
    sess_alt = httpx.Client(headers=headers, cookies=cookies.get('alt'))
    return sess_main, sess_alt


class Fetcher:
    def __init__(self):
        self.sess_main, self.sess_alt = _get_session()
        self._alt_login = None
        with Path(__file__).with_name('X-Bogus.js').open() as fp:
            ENV_NODE_JS = Path(__file__).resolve().parent.parent
            self.js_func = execjs.compile(
                fp.read(), cwd=ENV_NODE_JS/'node_modules')
        self.visits = 0
        self._visit_count = 0
        self._last_fetch = time.time()
        self.enable_pause = True

    @property
    def alt_login(self):
        return self._alt_login

    def toggle_alt(self, on: bool = False):
        if self._alt_login == on:
            return
        self._alt_login = on
        nickname = self.login(alt_login=on)
        console.log(
            f'fetcher: current logined as {nickname} (is_alt:{on})',
            style='green on dark_green')

    def login(self, alt_login: bool = False):
        session = self.sess_alt if alt_login else self.sess_main
        while True:
            r = self.get('https://www.douyin.com/user/self',
                         alt_login=alt_login)
            soup = BeautifulSoup(unquote(r.text), 'html.parser')
            for s in soup.find_all('script'):
                if 'realname' not in str(s).lower():
                    continue
                ptn = r'<script .*>self.__pace_f.push\(\[1,"(.*)"\]\)</script>'
                if m := re.search(ptn, str(s)):
                    login_status = json.loads(m.group(1))['app']['user']
                    break
            else:
                console.log(
                    f'cookie expired, relogin...(alt_login={alt_login})',
                    style='error')
                if not Confirm.ask('open browser to login?'):
                    raise ValueError('cookie expired')
                self._set_cookie(session)
                continue
            assert login_status.pop('isLogin') is True
            return login_status['info']['nickname']

    def _set_cookie(self, session):
        browser = webdriver.Chrome()
        browser.get('https://www.douyin.com/')
        input('press enter after login...')
        session.cookies = {c['name']: c['value']
                           for c in browser.get_cookies()}
        browser.quit()
        cookie_file = Path(__file__).with_name('cookie.json')
        cookies = dict(
            main={c.name: c.value for c in self.sess_main.cookies.jar},
            alt={c.name: c.value for c in self.sess_alt.cookies.jar})
        cookie_file.write_text(json.dumps(cookies))

    def _get_xbogus(self, params: dict | str) -> str:
        assert 'X-Bogus' not in params, 'X-Bogus in params'
        if isinstance(params, dict):
            params = urlencode(params)
        return self.js_func.call('sign', params, UA)

    def get(self, url: str | furl, params: dict = None,
            alt_login: bool | None = None):
        if alt_login is None:
            if self.alt_login is None:
                raise ValueError('alt_login is not set')
            alt_login = self.alt_login
        session = self.sess_alt if alt_login else self.sess_main
        if self.enable_pause:
            self._pause()
        console.log(f'fetching {url}...', style='info')
        url = furl(url)
        url.args |= params or {}
        url.args.pop('X-Bogus', None)
        url.args['X-Bogus'] = self._get_xbogus(url.query.encode())

        try_time = 0
        while True:
            try:
                r = session.get(str(url))
                r.raise_for_status()
            except (httpx.ConnectTimeout, httpx.ConnectTimeout):
                console.log('seems offline...sleep 10 secs', style='error')
                time.sleep(10)
            except httpx.PoolTimeout:
                console.log('pool timeout... sleep 10 secs', style='error')
                time.sleep(10)
            except httpx.HTTPError as e:
                period = 60
                try_time += 1
                if try_time > 10:
                    raise
                console.log(
                    f"{e}: Sleep {period} seconds and "
                    f"retry [link={url}]{url}[/link] at {try_time}th times",
                    style='error')
                time.sleep(period)
            else:
                assert r.status_code == 200
                return r

    def _pause(self):
        self.visits += 1
        if self._visit_count == 0:
            self._visit_count = 1
            self._last_fetch = time.time()
            return
        for flag in [2048, 1024, 256, 64, 32, 16]:
            if self._visit_count % flag == 0:
                sleep_time = flag * 2
                break
        else:
            sleep_time = 4

        sleep_time *= random.uniform(0.75, 1.25)
        self._last_fetch += sleep_time
        if (wait_time := (self._last_fetch-time.time())) > 0:
            console.log(
                f'sleep {wait_time:.1f} seconds...'
                f'(count: {self._visit_count})',
                style='info')
        elif wait_time < -3600:
            self._visit_count = 0
            console.log(
                f'reset visit count to {self._visit_count} since have '
                f'no activity for {-wait_time:.1f} seconds, '
                'which means more than 1 hour passed')
        else:
            console.log(
                f'no sleeping since more than {sleep_time:.1f} seconds passed'
                f'(count: {self._visit_count})')
        while time.time() < self._last_fetch:
            time.sleep(0.1)
        self._last_fetch = time.time()
        self._visit_count += 1


fetcher = Fetcher()
sess = httpx.Client(follow_redirects=True)


def download_single_file(
        url: str,
        filepath: Path,
        filename: str,
        xmp_info: dict = None,
        filesize: int = None,
        hash: str = None,
):
    filepath.mkdir(parents=True, exist_ok=True)
    img = filepath / filename
    if img.exists():
        console.log(f'{img} already exists..skipping...', style='info')
        return
    else:
        console.log(f'downloading {img}...', style="dim")
    for _ in range(10):
        try:
            r = sess.get(url, headers={'User-Agent': UA})
        except httpx.HTTPError as e:
            period = 60
            console.log(
                f"{e}: Sleepping {period} seconds and "
                f"retry [link={url}]{url}[/link]...", style='error')
            time.sleep(period)
            continue

        if r.status_code == 404:
            console.log(
                f"404 with normal fetch, using fetcher:{url}", style="info")
            r = fetcher.sess_main.get(url, follow_redirects=True)
            time.sleep(30)
            assert r.status_code == 200
        elif r.status_code != 200:
            console.log(f"{url}, {r.status_code}", style="error")
            time.sleep(15)
            console.log(f'retrying download for {url}...')
            continue

        elif not r.content:
            console.log(f"empty response for {url}", style="error")
            time.sleep(15)
            console.log(f'retrying download for {url}...')
            try:
                sess.get('https://www.douyin.com/', headers={'User-Agent': UA})
            except httpx.HTTPError:
                pass
            continue

        if int(r.headers['Content-Length']) != len(r.content):
            console.log(f"expected length: {r.headers['Content-Length']}, "
                        f"actual length: {len(r.content)} for {img}",
                        style="error")
            console.log(f'retrying download for {img}')
            continue
        f, h = len(r.content), hashlib.md5(r.content).hexdigest()
        if (f, h) != (filesize, hash) and (filesize or hash):
            console.log(f"expected size and hash: {filesize}, {hash}, "
                        f"actual: {f}, {h} for {img}",
                        style="error")

        img.write_bytes(r.content)

        if xmp_info:
            write_xmp(img, xmp_info)
        break
    else:
        raise ValueError(f'failed to download {url}')


def download_files(imgs: Iterable[dict]):
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(download_single_file, **img) for img in imgs]
    for future in futures:
        future.result()


def write_xmp(img: Path, tags: dict):
    for k, v in tags.copy().items():
        if isinstance(v, str):
            tags[k] = v.replace('\n', '&#x0a;')
    params = ['-overwrite_original', '-ignoreMinorErrors', '-escapeHTML']
    with ExifToolHelper() as et:
        ext = et.get_tags(img, 'File:FileTypeExtension')[
            0]['File:FileTypeExtension'].lower()
        if (suffix := f'.{ext}') != img.suffix:
            new_img = img.with_suffix(suffix)
            console.log(
                f'{img}: suffix is not right, moving to {new_img}...',
                style='error')
            img = img.rename(new_img)
        et.set_tags(img, tags, params=params)
