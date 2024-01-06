from datetime import datetime
from pathlib import Path
from typing import Iterator, Self

import pendulum
from peewee import Model
from playhouse.postgres_ext import (
    ArrayField,
    BigIntegerField,
    BooleanField, CharField,
    DateTimeTZField,
    ForeignKeyField,
    IntegerField, JSONField,
    PostgresqlExtDatabase,
    TextField
)
from playhouse.shortcuts import model_to_dict, update_model_from_dict

from aweme import console
from aweme.page import Page
from aweme.post import get_aweme, parse_aweme
from aweme.user import get_user

database = PostgresqlExtDatabase("aweme", host="localhost")


class BaseModel(Model):
    class Meta:
        database = database

    def __str__(self):
        model = model_to_dict(self, recurse=False)
        for k, v in model.items():
            if isinstance(v, datetime):
                model[k] = v.strftime("%Y-%m-%d %H:%M:%S")

        return "\n".join(f'{k}: {v}'.replace('\n', '  ') for k, v
                         in model.items() if v is not None)

    @classmethod
    def get_or_none(cls, *query, **filters) -> Self | None:
        return super().get_or_none(*query, **filters)

    @classmethod
    def get(cls, *query, **filters) -> Self:
        return super().get(*query, **filters)


class User(BaseModel):
    id = BigIntegerField(primary_key=True)
    sec_uid = CharField(unique=True)
    unique_id = CharField(unique=True)
    username = CharField()
    nickname = CharField()
    signature = CharField(null=True)
    school_name = CharField(null=True)
    age = IntegerField(null=True)
    gender = IntegerField(null=True)
    following_count = IntegerField()
    follower_count = IntegerField()
    followed = BooleanField()
    following = BooleanField()
    max_follower_count = IntegerField()
    aweme_count = IntegerField()
    forward_count = IntegerField()
    favoriting_count = IntegerField()
    total_favorited = IntegerField()
    show_favorite_list = BooleanField()
    province = CharField(null=True)
    city = CharField(null=True)
    district = CharField(null=True)
    ip = TextField(null=True)
    country = CharField(null=True)
    iso_country_code = CharField(null=True)
    homepage = TextField()
    avatar = TextField()
    signature_language = CharField()
    im_primary_role_id = IntegerField(null=True)
    im_role_ids = ArrayField(IntegerField, null=True)
    role_id = CharField(null=True)
    publish_landing_tab = IntegerField()
    follow_list_toast = IntegerField()
    has_subscription = BooleanField()
    live_commerce = BooleanField()
    public_collects_count = IntegerField()
    with_commerce_entry = BooleanField()
    with_fusion_shop_entry = BooleanField()
    show_subscription = BooleanField()
    mplatform_followers_count = IntegerField()
    is_mix_user = BooleanField()
    can_show_group_card = IntegerField()
    verification_type = IntegerField(null=True)
    custom_verify = CharField(null=True)
    douplus_user_type = IntegerField(null=True)
    mix_count = IntegerField()
    secret = IntegerField()
    new_friend_type = IntegerField()
    account_info_url = TextField(null=True)

    @classmethod
    def from_id(cls, user_id: str | int, update=False) -> Self:
        if isinstance(user_id, int) or user_id.isdigit():
            model = cls.get_or_none(id=user_id)
        else:
            user_id = user_id.split('?')[0].split('/')[-1]
            model = cls.get_or_none(sec_uid=user_id)
        if model and not update:
            return model
        user_dict = get_user(user_id)
        return cls.upsert(user_dict)

    @classmethod
    def upsert(cls, user_dict: dict) -> Self:
        user_id = user_dict['id']
        for k in (set(user_dict) - set(cls._meta.columns)):
            console.log(
                f'ignore unknow key=> {k}:{user_dict.pop(k)}', style='warning')

        if not (model := cls.get_or_none(cls.id == user_id)):
            user_dict['username'] = user_dict['nickname'].strip('-_')
            assert user_dict['username']
            cls.insert(user_dict).execute()
            return cls.get_by_id(user_id)
        model_dict = model_to_dict(model)
        for k, v in user_dict.items():
            assert v or v == 0
            if k in ['follower_count', 'max_follower_count',
                     'mplatform_followers_count', 'total_favorited',]:
                continue
            if v == model_dict[k]:
                continue
            console.log(f'+{k}: {v}', style='green bold on dark_green')
            if (ori := model_dict[k]) is not None:
                console.log(f'-{k}: {ori}', style='red bold on dark_red')
        cls.update(user_dict).where(cls.id == user_id).execute()
        return cls.get_by_id(user_id)

    def __str__(self):
        model = model_to_dict(self, recurse=False)
        for k in model.copy():
            if k in ['with_commerce_entry',
                     'with_fusion_shop_entry',
                     'has_subscription',
                     'live_commerce',
                     'show_subscription',
                     'show_favorite_list',
                     ]:
                if model[k] is False:
                    model.pop(k)
            elif k in ['public_collects_count', 'forward_count',
                       'favoriting_count', 'mix_count', 'secret',
                       'can_show_group_card', 'verification_type',
                       'new_friend_type']:
                if model[k] == 0:
                    model.pop(k)
        return "\n".join(f'{k}: {v}'.replace('\n', '  ') for k, v
                         in model.items() if v is not None)


class UserConfig(BaseModel):
    user = ForeignKeyField(User, backref="configs", unique=True)
    username = CharField()
    nickname = CharField()
    following = BooleanField()
    aweme_count = IntegerField()
    aweme_fetch = BooleanField(null=True)
    aweme_fetch_at = DateTimeTZField(null=True)
    aweme_cache_at = DateTimeTZField(null=True)
    aweme_next_fetch = DateTimeTZField(null=True)
    aweme_first_fetch = DateTimeTZField(null=True)
    signature = CharField(null=True)
    school_name = CharField(null=True)
    age = IntegerField(null=True)
    homepage = TextField()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.page = Page(self.user_id)

    @classmethod
    def from_id(cls, user_id: str | int) -> Self:
        user = User.from_id(user_id, update=True)
        user_dict = model_to_dict(user)
        user_dict['user_id'] = user_dict.pop('id')
        to_insert = {k: v for k, v in user_dict.items()
                     if k in cls._meta.columns}
        if cls.get_or_none(user_id=user.id):
            cls.update(to_insert).where(cls.user_id == user.id).execute()
        else:
            cls.insert(to_insert).execute()
        return cls.get(user_id=user.id)

    def get_homepage(self, since: pendulum.DateTime) -> Iterator['Post']:
        is_tops = []
        for aweme in self.page.homepage():
            is_top = aweme.pop('is_top')
            assert is_top in [0, 1]
            is_tops.append(is_top)
            aweme = Cache.add_cache(aweme).parse()
            if (create_time := aweme['create_time']) < since:
                if is_top:
                    console.log('skip top aweme')
                    continue
                else:
                    console.log(f'time {create_time:%y-%m-%d} is before '
                                f'{since:%y-%m-%d}, finished!')
                    break
            aweme = Post.upsert(aweme)
            yield aweme
        assert sorted(is_tops, reverse=True) == is_tops

    def _caching_aweme_for_new(self):
        if self.aweme_fetch is not None:
            assert self.aweme_cached_at is None
            assert self.aweme_fetch or self.aweme_fetch_at
            return
        else:
            assert self.aweme_fetch_at is None
        since = self.aweme_cache_at or pendulum.from_timestamp(0)
        console.log(
            f"caching {self.username}'s homepage (cached_at {since:%y-%m-%d})")
        now, i = pendulum.now(), 0
        for i, aweme in enumerate(self.get_homepage(since=since), start=1):
            console.log(aweme, '\n')
        console.log(f'{i} awemes cached for {self.username}')
        self.aweme_cache_at = now
        self.save()

    def fetch_aweme(self, download_dir: Path):
        # TODO: fetch aweme
        if self.aweme_fetch is None:
            self._caching_aweme_for_new()
            return
        elif self.aweme_fetch is False:
            return
        if self.aweme_fetch_at:
            pass


class Cache(BaseModel):
    id = BigIntegerField(primary_key=True)
    user_id = BigIntegerField()
    from_timeline = JSONField(null=True)
    from_page = JSONField(null=True)

    @classmethod
    def from_id(cls, aweme_id: int, update=False) -> dict:
        if not update and (cache := cls.get_or_none(id=aweme_id)):
            return cache.parse()
        cache = get_aweme(aweme_id)
        cache = cls.add_cache(cache)
        return cache.parse()

    def parse(self):
        self._check_parse()
        if self.from_page:
            return parse_aweme(self.from_page)
        else:
            assert self.from_timeline
            aweme = parse_aweme(self.from_timeline)
            if aweme['is_video'] and 'video_size' not in aweme:
                return self.from_id(self.id, update=True)
            return aweme

    @classmethod
    def add_cache(cls, aweme: dict) -> Self:
        aweme_id, user_id = aweme['aweme_id'], aweme['author_user_id']
        row = dict(id=aweme_id, user_id=user_id)
        if aweme['aweme_from'] == 'page':
            row['from_page'] = aweme
        else:
            assert aweme['aweme_from'] == 'timeline'
            row['from_timeline'] = aweme
        if (cache := cls.get_or_none(id=aweme_id)):
            update_model_from_dict(cache, row)
            cache.save()
        else:
            cls.insert(row).execute()
        cache = cls.get_by_id(aweme_id)
        cache._check_parse()
        return cache

    def _check_parse(self):
        if not (self.from_page and self.from_timeline):
            return
        d1, d2 = parse_aweme(self.from_page), parse_aweme(self.from_timeline)
        if set(d1) != set(d2):
            assert set(d1) == set(d2) | {'video_size', 'video_hash'}
        for k in d2:
            if k in ['img_urls', 'video_url', 'aweme_from']:
                continue
            if d1[k] != d2[k]:
                assert 'video_size' not in d2
                assert k in ['duration', 'bit_rate', 'height',
                             'width', 'FPS', 'gear_name', 'ratio']
                assert d1[k] > d2[k] or k in ['gear_name', 'width', 'height']


class Post(BaseModel):
    id = BigIntegerField(primary_key=True)
    user = ForeignKeyField(User, backref="posts")
    sec_uid = TextField()
    username = CharField()
    nickname = CharField()
    create_time = DateTimeTZField()
    desc = TextField(null=True)
    blog_url = TextField()
    address = JSONField(null=True)
    region = TextField(null=True)
    tags = ArrayField(CharField, null=True)
    at_users = ArrayField(CharField, null=True)
    video_tag = ArrayField(CharField)
    admire_count = IntegerField()
    collect_count = IntegerField()
    comment_count = IntegerField()
    digg_count = IntegerField()
    play_count = IntegerField()
    share_count = IntegerField()
    user_digged = IntegerField()
    collect_stat = IntegerField()
    img_ids = ArrayField(CharField, null=True)
    img_urls = ArrayField(TextField, null=True)
    video_id = CharField(null=True)
    video_url = TextField(null=True)
    video_size = IntegerField(null=True)
    video_hash = CharField(null=True)
    duration = IntegerField(null=True)
    bit_rate = IntegerField(null=True)
    height = IntegerField(null=True)
    width = IntegerField(null=True)
    is_source_HDR = IntegerField(null=True)
    is_long_vide = IntegerField(null=True)
    is_video = BooleanField()
    is_h265 = BooleanField(null=True)
    is_bytevc1 = BooleanField(null=True)
    is_life_item = BooleanField()
    is_story = BooleanField()
    is_image_beat = BooleanField()
    is_multi_content = IntegerField(null=True)
    category_da = IntegerField(null=True)

    FPS = IntegerField(null=True)
    gear_name = CharField(null=True)
    ratio = CharField(null=True)
    aweme_from = CharField()
    aweme_type = CharField()
    danmaku_cnt = IntegerField(null=True)
    original = IntegerField()
    preview_video_status = IntegerField()
    download_mask_panel = IntegerField()
    group_id = BigIntegerField()
    comment_gid = BigIntegerField()
    unknown_fields = JSONField(null=True)
    activity_video_type = IntegerField()

    @classmethod
    def from_id(cls, aweme_id: int, update=False):
        if not update and (awe := cls.get_or_none(id=aweme_id)):
            return awe
        else:
            aweme_dict = Cache.from_id(aweme_id, update=update)
            return cls.upsert(aweme_dict)

    @classmethod
    def upsert(cls, aweme_dict: dict) -> Self:
        id = aweme_dict['id']
        assert Cache.get_or_none(id=id)
        unknown = {}
        for k in (set(aweme_dict) - set(cls._meta.columns)):
            unknown[k] = aweme_dict.pop(k)
        if unknown:
            console.log(
                f'find unknow fields: {unknown}', style='warning')
        assert 'unknown_fields' not in aweme_dict
        aweme_dict['unknown_fields'] = unknown or None
        aweme_dict['username'] = User.get_by_id(aweme_dict['user_id']).username

        if not (model := cls.get_or_none(cls.id == id)):
            cls.insert(aweme_dict).execute()
            return cls.get(id=id)
        model_dict = model_to_dict(model, recurse=False)
        model_dict['user_id'] = model_dict.pop('user')
        for k, v in aweme_dict.items():
            assert v or v == 0 or k == 'unknown_fields'
            if v == model_dict[k] or k in ['img_urls', 'video_url']:
                continue
            console.log(f'+{k}: {v}', style='green bold on dark_green')
            if (ori := model_dict[k]) is not None:
                console.log(f'-{k}: {ori}', style='red bold on dark_red')
        cls.update(aweme_dict).where(cls.id == id).execute()
        return cls.get(id=id)


database.create_tables(
    [User, UserConfig, Post, Cache])
