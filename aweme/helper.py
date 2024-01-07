import itertools

from geopy.distance import geodesic

from aweme import console


def sort_dict(d):
    if isinstance(d, dict):
        return {k: sort_dict(v) if isinstance(v, (dict, list)) else v for k, v in sorted(d.items())}
    elif isinstance(d, list):
        return [sort_dict(item) if isinstance(item, (dict, list)) else item for item in d]
    else:
        return d


def round_loc(lat: float | str, lng: float | str,
              tolerance: float = 0.01) -> tuple[float, float]:
    """
    return rounded location with err small than tolerance meter
    """
    lat, lng = float(lat), float(lng)
    while True:
        for precision in itertools.count(start=1):
            lat_, lng_ = round(lat, precision), round(lng, precision)
            if (err := geodesic((lat, lng), (lat_, lng_)).meters) < tolerance:
                break
        if err:
            console.log(
                f'round loction: {lat, lng} -> {lat_, lng_} '
                f'with precision {precision} (err: {err}m)')
            lat, lng = lat_, lng_
        else:
            break
    return lat_, lng_


DICT_CMP_USER = {
    'apple_account': 0,
    'aweme_count_correction_threshold': -1,
    'can_set_item_cover': False,
    'close_friend_type': 0,
    'commerce_info': {'challenge_list': None,
                      'head_image_list': None,
                      'offline_info_list': [],
                      'smart_phone_list': None,
                      'task_list': None},
    'commerce_user_level': 0,
    'has_e_account_role': False,
    'image_send_exempt': False,
    'ins_id': '',
    'is_ban': False,
    'is_block': False,
    'is_blocked': False,
    'is_effect_artist': False,
    'is_gov_media_vip': False,
    'is_not_show': False,
    'is_series_user': False,
    'is_sharing_profile_user': 0,
    'is_star': False,
    'is_top': 0,
    'life_story_block': {'life_story_block': False},
    'original_musician': {'digg_count': 0,
                          'music_count': 0,
                          'music_used_count': 0},
    'pigeon_daren_status': '',
    'pigeon_daren_warn_tag': '',
    'profile_tab_type': 0,
    'r_fans_group_info': {},
    'recommend_reason_relation': '',
    'recommend_user_reason_source': 0,
    'risk_notice_text': '',
    'series_count': 0,
    'special_follow_status': 0,
    'sync_to_toutiao': 0,
    'tab_settings': {'private_tab': {'private_tab_style': 1,
                                     'show_private_tab': False}},
    'total_favorited_correction_threshold': -1,
    'twitter_id': '',
    'twitter_name': '',
    'urge_detail': {'user_urged': 0},
    'video_cover': {},
    'video_icon': {'height': 720, 'uri': '', 'url_list': [], 'width': 720},
    'watch_status': False,
    'with_commerce_enterprise_tab_entry': False,
    'with_new_goods': False,
    'youtube_channel_id': '',
    'enable_ai_double': 0,
    'enable_wish': False,
    'enterprise_verify_reason': '',
    'favorite_permission': 1,
    'dynamic_cover': {},
    'is_activity_user': False,
    'follower_request_status': 0,
    'dongtai_count': 0,
    'message_chat_entry': True,
    'user_not_see': 0,
    'user_not_show': 1,

    'youtube_channel_title': ''}

DICT_CMP_AWEME = {
    'author_mask_tag': 0,
    'aweme_control': {
        'can_forward': True,
        'can_share': True,
        'can_comment': True,
        'can_show_comment': True},
    'boost_status': 0,
    'charge_info': {'is_charge_content': False, 'is_subscribe_content': False},
    'collection_corner_mark': 0,
    'comment_permission_info': {
        'comment_permission_status': 0,
        'can_comment': True,
        'item_detail_entry': False,
        'press_entry': False,
        'toast_guide': False},
    'common_bar_info': '[]',
    'component_info_v2': '{"desc_lines_limit":0,"hide_marquee":false}',
    'disable_relation_bar': 0,
    'distribute_circle': {
        'distribute_type': 0,
        'campus_block_interaction': False,
        'is_campus': False},
    'duet_aggregate_in_music_tab': False,
    'image_crop_ctrl': 0,
    'is_collects_selected': 0,
    'is_duet_sing': False,
    'is_share_post': False,
    'item_title': '',
    'item_warn_notification': {'type': 0, 'show': False, 'content': ''},

    'series_paid_info': {'series_paid_status': 0, 'item_price': 0},
    'should_open_ad_report': False,

    'user_recommend_status': 0,

}
