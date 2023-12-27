import os
import time
from pathlib import Path
from urllib.parse import urlencode

import execjs
import requests
from dotenv import load_dotenv
from furl import furl

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

    def _get_xbogus(self, params: dict | str) -> str:
        assert 'X-Bogus' not in params, 'X-Bogus in params'
        if isinstance(params, dict):
            params = urlencode(params)
        return self.js_func.call('sign', params, UA)

    def get(self, url: str | furl, params: dict = None):
        url = furl(url)
        url.args |= params or {}
        url.args.pop('X-Bogus', None)
        url.args['X-Bogus'] = self._get_xbogus(url.query.encode())
        return self.session.get(url)


fetcher = Fetcher()


def get_user(user_id):
    user_id = user_id.split('?')[0].split('/')[-1]
    params = {
        'sec_user_id': user_id,
        'aid': '6383',
        'version_code': '170400',
    }
    url = "https://www.douyin.com/aweme/v1/web/user/profile/other/"
    return fetcher.get(url, params=params)


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
