from typing import Self

from furl import furl

from aweme.fetcher import fetcher
from aweme.helper import sort_dict


class Page:
    def __init__(self, user_id: int | str):
        self.user_id = user_id

    @classmethod
    def get_self_page(cls) -> Self:
        url = 'https://www.douyin.com/aweme/v1/web/query/user/?device_platform=webapp&aid=6383&version_code=170400'
        user_id = fetcher.get(url).json()['user_uid']
        return cls(user_id)

    @property
    def uid_map(self) -> dict:
        if isinstance(self.user_id, str) and not self.user_id.isdigit():
            return {'sec_user_id': self.user_id}
        else:
            return {'user_id': int(self.user_id)}

    def homepage(self):
        f = furl('https://www.douyin.com/aweme/v1/web/aweme/post/')
        f.args = {
            'aid': '6383',
            'count': '18',
            'version_code': '170400',
        }
        f.args |= self.uid_map
        aweme_times, aweme_ids = [], []
        while True:
            js = fetcher.get(f).json()
            assert js.pop('status_code') == 0
            for aweme in js.pop('aweme_list'):
                if not aweme['is_top']:
                    aweme_times.append(aweme['create_time'])
                    aweme_ids.append(aweme['aweme_id'])
                assert 'aweme_from' not in aweme
                aweme['aweme_from'] = 'timeline'
                yield sort_dict(aweme)
            if js.pop('has_more'):
                f.args['max_cursor'] = js['max_cursor']
            else:
                break
        assert sorted(aweme_times, reverse=True) == aweme_times
        assert sorted(aweme_ids, reverse=True) == aweme_ids

    def get_following(self):
        url = furl('https://www.douyin.com/aweme/v1/web/user/following/list/')
        url.args = {
            'aid': '6383',
            'max_time': '0',
            'source_type': '1',
            'version_code': '170400',
        }
        url.args |= self.uid_map
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
