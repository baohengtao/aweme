from furl import furl
from typer import Typer

from aweme import console
from aweme.fetcher import fetcher
from aweme.model import User

from .helper import logsaver_decorator

app = Typer()


def get_self_id():
    url = 'https://www.douyin.com/aweme/v1/web/query/user/?device_platform=webapp&aid=6383&version_code=170400'
    return fetcher.get(url).json()['user_uid']


def get_following():
    url = furl('https://www.douyin.com/aweme/v1/web/user/following/list/')
    url.args = {
        'aid': '6383',
        'user_id': get_self_id(),
        'max_time': '0',
        'source_type': '1',
        'version_code': '170400',
    }
    while True:
        js = fetcher.get(url).json()
        for f in js['followings']:
            keeped_key = [
                'nickname',
                'relation_label',
                'sec_uid',
                'short_id',
                'status',
                'uid',
                'unique_id',
            ]
            f = {k: v for k, v in f.items() if k in keeped_key and v not in [
                None, '', []]}
            f['homepage'] = f'https://www.douyin.com/user/{f["sec_uid"]}'
            yield f
        if not js['has_more']:
            break
        url.args['max_time'] = js['min_time']


@app.command()
@logsaver_decorator
def user_add():
    for f in get_following():
        console.log(f'fetching {f["homepage"]}')
        console.log(User.from_id(f['uid'], update=True), '\n')
