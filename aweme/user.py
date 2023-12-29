import requests

from aweme.fetcher import fetcher
from aweme.helper import DICT_CMP_USER


def get_user(user_id: int | str, parse=True):
    params = {
        'aid': '6383',
        'version_code': '170400',
    }

    if isinstance(user_id, int) or user_id.isdigit():
        params['user_id'] = user_id
    else:
        sec_user_id = user_id.split('?')[0].split('/')[-1]
        params['sec_user_id'] = sec_user_id

    url = "https://www.douyin.com/aweme/v1/web/user/profile/other/"
    response = fetcher.get(url, params=params)
    return parse_user(response) if parse else response


def parse_user(r: requests.Response):
    # process js
    js = r.json()
    assert js.pop('status_code') == 0
    assert js.pop('status_msg') is None
    extra = js.pop('extra')

    assert js.pop('log_pb') == {'impr_id': extra.pop('logid')}
    assert extra.pop('fatal_item_ids') == []
    assert list(extra.keys()) == ['now']
    assert list(js.keys()) == ['user']

    # process user
    user = js.pop('user')
    # process avatar
    avatar = user.pop('avatar_larger')['url_list']
    assert len(avatar) == 1
    assert 'avatar' not in user
    user['avatar'] = avatar[0].split('?')[0]
    # remove useless keys
    useless_keys = [
        'share_info', 'white_cover_url',
        'cover_and_head_image_info', 'cover_url', 'cover_colour',
        'avatar_168x168', 'avatar_300x300', 'avatar_medium', 'avatar_thumb'
    ]
    for key in useless_keys:
        user.pop(key)
    user.pop('signature_extra', None)
    assert user.pop('province') in ['', None]
    assert user.pop('mplatform_followers_count') == user['follower_count']
    # process ip_location
    ip_location = user.pop('ip_location')
    assert ip_location.startswith('IP属地：')
    assert 'ip' not in user
    user['ip'] = ip_location.removeprefix('IP属地：')
    # process age
    assert 'age' not in user
    user['age'] = user.pop('user_age')
    # process id
    assert 'id' not in user
    user['id'] = int(user.pop('uid'))

    # process homepage
    assert 'homepage' not in user
    user['homepage'] = f'https://douyin.com/user/{user["sec_uid"]}'

    for k, v in DICT_CMP_USER.items():
        assert user.pop(k) == v
    reorder = [
        'id', 'sec_uid', 'unique_id', 'nickname',  'signature', 'school_name',
        'age', 'gender', 'following_count', 'follower_count',
        'max_follower_count', 'aweme_count', 'forward_count',
        'favoriting_count', 'total_favorited', 'show_favorite_list',
        'city',  'district', 'ip', 'country', 'iso_country_code', 'homepage',
        'avatar', 'signature_language', 'im_primary_role_id', 'im_role_ids',
        'publish_landing_tab'
    ]
    user1 = {k: user[k] for k in reorder if k in user}
    user2 = {k: user[k] for k in user if k not in reorder}
    user = user1 | user2

    return {k: v for k, v in user.items() if v not in [None, '', []]}
