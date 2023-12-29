import os
import random
import time
from pathlib import Path
from urllib.parse import urlencode

import execjs
import requests
from dotenv import load_dotenv
from furl import furl

from aweme import console

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _get_session():
    env_file = Path(__file__).with_name('.env')
    load_dotenv(env_file)
    if not (COOKIE := os.getenv('COOKIE')):
        raise ValueError(f'no cookie found in {env_file}')
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
        "cookie": COOKIE
    }
    return session


class Fetcher:
    def __init__(self):
        self.session = _get_session()
        with Path(__file__).with_name('X-Bogus.js').open() as fp:
            ENV_NODE_JS = Path(__file__).resolve().parent.parent
            self.js_func = execjs.compile(
                fp.read(), cwd=ENV_NODE_JS/'node_modules')
        self.visits = 0
        self._visit_count = 0
        self._last_fetch = time.time()

    def _get_xbogus(self, params: dict | str) -> str:
        assert 'X-Bogus' not in params, 'X-Bogus in params'
        if isinstance(params, dict):
            params = urlencode(params)
        return self.js_func.call('sign', params, UA)

    def get(self, url: str | furl, params: dict = None):
        self._pause()
        url = furl(url)
        url.args |= params or {}
        url.args.pop('X-Bogus', None)
        url.args['X-Bogus'] = self._get_xbogus(url.query.encode())
        return self.session.get(url)

    def _pause(self):
        self.visits += 1
        if self._visit_count == 0:
            self._visit_count = 1
            self._last_fetch = time.time()
            return
        for flag in [2048, 1024, 256, 64, 16]:
            if self._visit_count % flag == 0:
                sleep_time = flag
                break
        else:
            sleep_time = 1
        sleep_time *= random.uniform(0.5, 1.5)
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


def get_post(user_id):
    user_id = user_id.split('?')[0].split('/')[-1]
    params = {
        'sec_user_id': user_id,
        'max_cursor': int(time.time())*1000,
        'count': 100,
        'publish_video_strategy_type': '2',
        'aid': '6383',
    }
    url = "https://www.douyin.com/aweme/v1/web/aweme/post/"
    response = fetcher.get(url, params=params)
    return response
