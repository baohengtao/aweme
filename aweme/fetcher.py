import hashlib
import json
import pickle
import random
import re
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlencode

import execjs
import requests
from bs4 import BeautifulSoup
from exiftool import ExifToolHelper
from furl import furl
from requests.exceptions import ConnectionError
from selenium import webdriver

from aweme import console

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _get_session():
    session = requests.session()
    session.headers = {
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
    return session


class Fetcher:
    def __init__(self):
        self.session = _get_session()
        self.login_status = None
        with Path(__file__).with_name('X-Bogus.js').open() as fp:
            ENV_NODE_JS = Path(__file__).resolve().parent.parent
            self.js_func = execjs.compile(
                fp.read(), cwd=ENV_NODE_JS/'node_modules')
        self.visits = 0
        self._visit_count = 0
        self._last_fetch = time.time()
        self.enable_pause = True
        self.deque = deque(maxlen=5)

    def get_login_status(self):
        r = self.session.get('https://www.douyin.com/user/self')
        soup = BeautifulSoup(unquote(r.text), 'html.parser')
        for s in soup.find_all('script'):
            if 'realname' not in str(s).lower():
                continue
            ptn = r'<script .*>self.__pace_f.push\(\[1,"(.*)"\]\)</script>'
            if m := re.search(ptn, str(s)):
                login_status = json.loads(m.group(1))['app']['user']
                break
        else:
            return
        assert login_status.pop('isLogin') is True
        nickname = login_status['info']['nickname']
        console.log(f'current logined as {nickname}', style='info')
        self.login_status = nickname
        return nickname

    def get_cookie(self):
        cookie_file = Path(__file__).with_name('cookie.pkl')
        if cookie_file.exists():
            self.session.cookies = pickle.loads(cookie_file.read_bytes())
            if self.get_login_status():
                return
        browser = webdriver.Chrome()
        browser.get('https://www.douyin.com/')
        input('press enter after login...')
        for cookie in browser.get_cookies():
            for k in ['expiry', 'httpOnly', 'sameSite']:
                cookie.pop(k, None)
            self.session.cookies.set(**cookie)
        cookie_file.write_bytes(pickle.dumps(self.session.cookies))
        browser.quit()
        assert self.get_login_status()

    def _get_xbogus(self, params: dict | str) -> str:
        assert 'X-Bogus' not in params, 'X-Bogus in params'
        if isinstance(params, dict):
            params = urlencode(params)
        return self.js_func.call('sign', params, UA)

    def get(self, url: str | furl, params: dict = None):
        if not self.login_status:
            self.get_cookie()
        if self.enable_pause:
            self._pause()
        console.log(f'fetching {url}...', style='info')
        url = furl(url)
        url.args |= params or {}
        url.args.pop('X-Bogus', None)
        url.args['X-Bogus'] = self._get_xbogus(url.query.encode())

        while True:
            try:
                r = self.session.get(url)
                r.raise_for_status()
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.HTTPError) as e:
                period = 60
                console.log(
                    f"{e}: Sleepping {period} seconds and "
                    f"retry [link={url}]{url}[/link]...", style='error')
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
        for flag in [2048, 1024, 256, 64, 32]:
            if self._visit_count % flag == 0:
                sleep_time = flag * 2
                break
        else:
            sleep_time = 32

        sleep_time *= random.uniform(0.75, 1.25)
        self._last_fetch += sleep_time
        if len(self.deque) == 5:
            self._last_fetch = max(self._last_fetch, self.deque[0]+300)
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
        self.deque.append(self._last_fetch)
        self._visit_count += 1


fetcher = Fetcher()


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
    while True:
        try:
            r = requests.get(url, headers={'User-Agent': UA})
        except ConnectionError as e:
            period = 60
            console.log(
                f"{e}: Sleepping {period} seconds and "
                f"retry [link={url}]{url}[/link]...", style='error')
            time.sleep(period)
            continue

        if r.status_code == 404:
            console.log(
                f"404 with normal fetch, using fetcher:{url}", style="info")
            r = fetcher.session.get(url)
            time.sleep(30)
            assert r.status_code == 200
            # console.log(
            #     f"{url}, {xmp_info}, {r.status_code}", style="error")
            # return
        elif r.status_code != 200:
            console.log(f"{url}, {r.status_code}", style="error")
            time.sleep(15)
            console.log(f'retrying download for {url}...')
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
