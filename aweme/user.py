import requests

from aweme import console
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
    response = fetcher.get(url, params=params, alt_login=False)
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
        'avatar_168x168', 'avatar_300x300', 'avatar_medium', 'avatar_thumb',
        'signature_display_lines', 'urge_detail', 'sync_to_toutiao',
        'enterprise_user_info', 'commerce_user_info', 'signature_language',
    ]
    for key in useless_keys:
        user.pop(key)
    useless_keys_opt = [
        'commerce_info', 'card_entries', 'signature_extra',
        'account_info_url', 'iso_country_code', 'official_cooperation',
        'im_primary_role_id', 'im_role_ids', 'role_id',
    ]
    for key in useless_keys_opt:
        user.pop(key, None)

    # process short_id
    if (short_id := user.pop('short_id')) != '0':
        assert user['unique_id'] == ''
        assert short_id.isdigit()
        user['unique_id'] = short_id

    # process ip_location
    if ip := user.pop('ip_location', None):
        assert ip.startswith('IP属地：')
        assert 'ip' not in user
        user['ip'] = ip.removeprefix('IP属地：')
    # process age
    age = user.pop('user_age')
    if (b := user.pop('birthday_hide_level')) == 1:
        assert age == -1
    else:
        assert b == 0
        assert 'age' not in user
        if age != -1:
            assert age > 0
            user['age'] = age
    # process id
    assert 'id' not in user
    user['id'] = int(user.pop('uid'))

    # process homepage
    assert 'homepage' not in user
    user['homepage'] = f'https://douyin.com/user/{user["sec_uid"]}'

    if (d := user.pop('general_permission', None)):
        assert d == {'following_follower_list_toast': 1}
        follow_list_toast = 1
    else:
        follow_list_toast = 0
    assert 'follow_list_toast' not in user
    user['follow_list_toast'] = follow_list_toast

    if (u := user.pop('user_permissions', None)):
        assert len(u) == 1 and len(u[0]) == 2
        u = u[0]
        assert u['key'] == 'douplus_user_type'
        assert 'douplus_user_type' not in user
        user['douplus_user_type'] = int(u['value'])
    assert user.pop('favorite_permission') == 1 - user['show_favorite_list']

    # process living
    if (lstatus := user.pop('live_status')) == 0:
        assert user.pop('room_id') == 0
    else:
        assert lstatus == 1
        assert user.pop('room_id') == int(user.pop('room_id_str')) > 0
        assert user.pop('room_data')
        console.log('🎀 find living: '
                    f'[link={user["homepage"]}]{user["nickname"]}[/link]',
                    style='green on dark_green')

    not_match = {}
    for k, v in DICT_CMP_USER.items():

        if user.get(k) != v:
            not_match[k] = (user.get(k), v)
        else:
            assert user.pop(k) == v
    if not_match:
        console.log(
            f'{user["homepage"]}: not matching=>{not_match}', style='error')
    # process following info
    follow_status = user.pop('follow_status')
    follower_status = user.pop('follower_status')
    if follow_status == 2:
        assert follower_status == 1
    else:
        assert follower_status in [0, 1]
        assert follow_status in [0, 1]
    assert 'following' not in user
    assert 'followed' not in user
    user['following'] = bool(follow_status)
    user['followed'] = bool(follower_status)

    if not user['following']:
        assert user.pop('follow_guide') is True
    else:
        assert user.pop('is_top') == 0

    if remark := user.pop('remark_name', None):
        assert 'username' not in user
        user['username'] = remark
    reorder = [
        'id', 'sec_uid', 'unique_id', 'username', 'nickname',  'signature',
        'school_name', 'age', 'gender', 'following', 'following_count',
        'follower_count', 'max_follower_count', 'aweme_count', 'forward_count',
        'favoriting_count', 'total_favorited', 'show_favorite_list',
        'city',  'district', 'ip', 'country', 'province',
        'homepage', 'avatar',
        'publish_landing_tab'
    ]
    user1 = {k: user[k] for k in reorder if k in user}
    user2 = {k: user[k] for k in user if k not in reorder}
    user = user1 | user2

    return {k: v for k, v in user.items() if v not in [None, '', [], '{}', '0']}
