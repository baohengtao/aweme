import json
import re
from copy import deepcopy

import pendulum
from furl import furl

from aweme import console
from aweme.fetcher import fetcher
from aweme.helper import DICT_CMP_AWEME, round_loc, sort_dict


def get_aweme(aweme_id: int) -> dict:
    url = furl('https://www.douyin.com/aweme/v1/web/aweme/detail/')
    url.args = {'device_platform': 'webapp',
                'aid': '6383',
                'channel': 'channel_pc_web',
                'aweme_id': aweme_id,
                'pc_client_type': '1',
                'version_code': '190500',
                'version_name': '19.5.0',
                'cookie_enabled': 'true',
                'screen_width': '1920',
                'screen_height': '1080',
                'browser_language': 'en-US',
                'browser_platform': 'MacIntel',
                'browser_name': 'Chrome',
                'browser_version': '120.0.0.0',
                'browser_online': 'true',
                'engine_name': 'Blink',
                'engine_version': '120.0.0.0',
                'os_name': 'Mac OS',
                'os_version': '10.15.7',
                'cpu_core_num': '8',
                'device_memory': '8',
                'platform': 'PC',
                'downlink': '10',
                'effective_type': '4g',
                'round_trip_time': '50',
                'webid': '7311600805983176230',
                }
    js = fetcher.get(url).json()
    assert set(js.keys()) == {'aweme_detail', 'log_pb', 'status_code'}
    assert js.pop('status_code') == 0
    aweme = js.pop('aweme_detail')
    assert 'aweme_from' not in aweme
    aweme['aweme_from'] = 'page'
    return sort_dict(aweme)


def parse_aweme(aweme):

    aweme = deepcopy(aweme)

    # remove useless keys
    useless_keys = [
        'image_album_music_info', 'video_control',
        'visual_search_info', 'is_use_music', 'impression_data', 'share_info',
        'photo_search_entrance', 'authentication_token', 'interaction_stickers',
        'entertainment_product_info', 'comment_permission_info', 'boost_status',
        'risk_infos', 'xigua_base_info',  'status',
    ]
    for key in useless_keys:
        aweme.pop(key)

    useless_keys_opt = [
        'vtag_search', 'main_arch_common', 'music', 'seo_info',
        'charge_info', 'fall_card_struct', 'incentive_item_type',
        'enable_comment_sticker_rec', 'share_url',
        'duet_origin_item', 'duet_origin_item_id',
        'guide_scene_info', 'should_open_ad_report', 'is_share_post',
        'report_action', 'comment_words_recommend', 'common_bar_info',
        'is_ads',
    ]
    for key in useless_keys_opt:
        aweme.pop(key, None)

    assert aweme.pop('preview_title', '') in aweme['desc']
    if aweme['mark_largely_following'] is False:
        assert aweme.pop('mark_largely_following') is False
    if dmp := aweme.pop('aweme_acl', None):
        assert dmp == {'download_mask_panel': {'code': 1, 'show_type': 0}}
        aweme['download_mask_panel'] = 1
    else:
        aweme['download_mask_panel'] = 0

    assert aweme.pop('guide_btn_type') == 0
    assert aweme.pop('prevent_download') is False

    for k, v in DICT_CMP_AWEME.items():
        if k not in aweme:
            console.log(f'missing key=>{k}:{v}', style='error')
        elif aweme[k] != v:
            console.log(
                f'not matching for key {k}=>{(aweme[k], v)}', style='error')
        else:
            assert aweme.pop(k) == v

    # extra basic info
    author = aweme.pop('author')
    tags, at_users = [], []
    for extra in aweme.pop('text_extra'):
        if set(extra) == {'caption_end', 'caption_start', 'end', 'start', 'type'}:
            assert extra['type'] not in [0, 1]
            continue
        if extra['type'] == 1:
            assert set(extra.keys()).issubset({
                'start', 'end', 'type', 'hashtag_name',
                'hashtag_id', 'is_commerce', 'caption_start', 'caption_end'})
            tags.append(extra['hashtag_name'])
        elif extra['type'] == 0:
            extra.pop('aweme_id', None)
            extra.pop('sub_type', None)
            assert set(extra.keys()) == {
                'caption_end', 'caption_start', 'end',
                'sec_uid', 'start', 'type', 'user_id'}
            at_users.append(extra['sec_uid'])
        else:
            raise ValueError(extra)
    if aweme['images']:
        blog_url = f'https://www.douyin.com/note/{aweme["aweme_id"]}'
    else:
        blog_url = f'https://www.douyin.com/video/{aweme["aweme_id"]}'
    result = {
        'aweme_id': (aweme_id := aweme.pop('aweme_id')),
        'user_id': int(author.pop('uid')),
        'sec_uid': author.pop('sec_uid'),
        'nickname': author.pop('nickname'),
        'create_time': pendulum.from_timestamp(
            aweme.pop('create_time'), tz='local'),
        'desc': aweme.pop('desc').strip(),
        'region': aweme.pop('region'),
        'tags': tags,
        'at_users': at_users,
        'blog_url': blog_url,
        'aweme_from': aweme.pop('aweme_from'),
        'aweme_type': aweme.pop('aweme_type'),
    }
    result['video_tag'] = [tag['tag_name']
                           for tag in aweme.pop('video_tag') if tag['tag_name']]

    statistics = aweme.pop('statistics')
    assert result | statistics == statistics | result
    result |= statistics

    media = process_media(aweme.pop('images'), aweme.pop('video'))
    assert result | media == media | result
    result |= media
    assert aweme.pop('media_type') == (4 if result['is_video'] else 2)
    try:
        result['aweme_type'] = {
            0: 'GENERAL',
            51: 'DUET_VIDEO',
            53: 'MV',
            55: 'STICK_POINT_VIDEO',
            61: 'IMAGE_VIDEO',
            66: 'RECOMMEND_TMPL_MV',
            68: 'IMAGE_PUBLISH',
            109: 'CANVAS',
            110: 'KARAOKE'
        }[result['aweme_type']]
    except KeyError:
        raise ValueError(result['aweme_type'],
                         aweme['search_impr']['entity_type'])

    assert result['user_id'] == aweme.pop('author_user_id')
    if search_impr := aweme.pop('search_impr', None):
        assert search_impr.pop('entity_id') == aweme_id
        assert result['aweme_type'] == search_impr.pop('entity_type')
        assert not search_impr

    if anchor_info := aweme.pop('anchor_info', None):
        assert 'address' not in result
        result['address'] = process_anchor(anchor_info)

    if dm := aweme.pop('danmaku_control', None):
        assert result['is_video'] is True
        assert 'danmaku_cnt' not in result
        result['danmaku_cnt'] = dm['danmaku_cnt']

    assert aweme.pop('duration') == result.get('duration', 0)

    assert aweme | result == result | aweme
    result |= aweme
    result = {k: v for k, v in result.items()
              if v not in [None, [], {}, '']}

    assert 'id' not in result
    result['id'] = int(result.pop('aweme_id'))
    result['group_id'] = int(result['group_id'])
    if result['is_video']:
        if (ht := result.pop('horizontal_type', None)) == 1:
            assert result['width'] > result['height']
        else:
            assert ht is None
            # assert result['width'] <= result['height']
    if 'caption' in result:
        assert re.sub(r'\s', '', result.pop('caption')
                      ) in re.sub(r'\s', '', result['desc'])

    # process mix info
    if mix_info := result.get('mix_info'):
        for key in ['cover_url', 'share_info', 'extra']:
            mix_info.pop(key)

    return result


def process_anchor(anchor_info):
    extra = json.loads(anchor_info['extra'])
    if 'address_info' not in extra:
        return
    ext_json = json.loads(extra['ext_json'])
    poi_prefix = ext_json['item_ext']['anchor_info'].get('type_name')
    address = extra.pop('address_info')
    info = {
        'id': extra["poi_id"],
        'location_prefix': poi_prefix,
        'location_name': extra["poi_name"],
        "longitude": extra["poi_longitude"],
        "latitude": extra["poi_latitude"],
    }
    info['latitude'], info['longitude'] = round_loc(
        info['latitude'], info['longitude'])
    assert address | info == info | address
    address |= info
    return address


def process_media(img_list, vid_dict):
    vid_dict = deepcopy(vid_dict)
    vid_dict.pop('audio', None)
    img_list = deepcopy(img_list)
    if img_list is None:
        return process_media_for_vid(vid_dict)
    img_ids = [img['uri'] for img in img_list]
    img_urls = [img['url_list'][0] for img in img_list]
    vid_dict.pop('big_thumbs')
    assert vid_dict.pop('bit_rate_audio') is None
    assert vid_dict.pop('cover')['uri'] in img_ids
    assert vid_dict.pop('origin_cover')['uri']
    assert vid_dict.pop('play_addr')
    assert vid_dict.pop('duration') == 0
    if 'has_watermark' in vid_dict:
        assert vid_dict.pop('has_watermark') is False
        assert vid_dict.pop('is_h265') == 0
    vid_dict.pop('meta')
    assert vid_dict.pop('ratio') == 'default'
    vid_dict = {k: v for k, v in vid_dict.items() if v not in [None, [], {}]}
    assert set(vid_dict.keys()) == {'height', 'width'},  set(vid_dict.keys())
    return dict(img_ids=img_ids, img_urls=img_urls, is_video=False)


def process_media_for_vid(vid_dict):
    vid_dict = deepcopy(vid_dict)
    # pop useless keys
    for k in ['cover', 'origin_cover', 'gaussian_cover',
              'dynamic_cover', 'meta', 'height', 'width',
              'big_thumbs', 'misc_download_addrs', 'cover_original_scale',
              'animated_cover', 'use_static_cover', 'optimized_cover',
              'horizontal_type', 'is_h265', 'cdn_url_expired', 'bit_rate_audio'
              ]:
        vid_dict.pop(k, None)

    assert 'uri' not in vid_dict
    vid_dict['uri'] = uri = vid_dict['play_addr']['uri']
    if 'download_addr' in vid_dict:
        assert vid_dict.pop('download_addr')['uri'] == uri
        if 'download_suffix_logo_addr' in vid_dict:
            assert vid_dict.pop('download_suffix_logo_addr')['uri'] == uri
            assert vid_dict.pop('has_download_suffix_logo_addr') is True
        assert vid_dict.pop('has_watermark') is True

    # process bit_rate
    bit_rate = vid_dict.pop('bit_rate')
    play_addrs = [b['play_addr'] for b in bit_rate]
    for key in ['play_addr', 'play_addr_265', 'play_addr_h264']:
        if play_addr := vid_dict.pop(key, None):
            if play_addr not in play_addrs:
                assert play_addr['uri'] == uri
                assert (play_addr['width']
                        <= bit_rate[0]['play_addr']['width'])
                assert (play_addr['height']
                        <= bit_rate[0]['play_addr']['height'])
    for b in bit_rate[1:]:
        if b['bit_rate'] > bit_rate[0]['bit_rate']:
            console.log(
                f'bit_rate is not maximum {b["bit_rate"], bit_rate[0]["bit_rate"]}', style='error')
        assert b['play_addr']['uri'] == uri
    assert vid_dict | bit_rate[0] == bit_rate[0] | vid_dict
    vid_dict |= bit_rate[0]
    assert vid_dict.pop('format', 'mp4') == 'mp4'

    # process play_addr
    play_addr = vid_dict.pop('play_addr')
    assert vid_dict | play_addr == play_addr | vid_dict
    vid_dict |= play_addr

    # get url
    url = vid_dict.pop('url_list')[-1]
    assert f'video_id={uri}' in url
    assert url.startswith('https://www.douyin.com/aweme/v1/play/?')
    assert 'url' not in vid_dict
    vid_dict['url'] = url

    # pop useless keys
    for k in ['video_extra', 'file_cs', 'url_key']:
        vid_dict.pop(k, None)
    assert vid_dict.pop('HDR_bit') == ''
    assert vid_dict.pop('HDR_type') == ''
    assert vid_dict.pop('video_model') == ''
    # assert vid_dict.pop('is_h265') == 0
    # assert vid_dict.pop('ratio') in ['1080p', '720p', '540p']
    # assert vid_dict.pop('gear_name') in [
    #     'adapt_1080_0', 'normal_1080_0', 'normal_720_0', 'normal_540_0']
    vid_dict.pop('quality_type')

    result = {
        'video_id': vid_dict.pop('uri'),
        'video_url': vid_dict.pop('url'),
        'video_size': vid_dict.pop('data_size', None),
        'video_hash': vid_dict.pop('file_hash', None),
        'duration': vid_dict.pop('duration'),
        'bit_rate': vid_dict.pop('bit_rate'),
        'height': vid_dict.pop('height'),
        'width': vid_dict.pop('width'),
        'is_source_HDR': vid_dict.pop('is_source_HDR'),
        'is_long_vide': vid_dict.pop('is_long_video', None),
        'is_video': True,
        'is_h265': vid_dict.pop('is_h265'),
        'is_bytevc1': vid_dict.pop('is_bytevc1'),
        'FPS': vid_dict.pop('FPS'),
        'gear_name': vid_dict.pop('gear_name'),
        'ratio': vid_dict.pop('ratio')
    }
    assert not vid_dict, vid_dict
    return result
