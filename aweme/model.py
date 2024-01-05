from datetime import datetime
from typing import Self

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
    follower_status = IntegerField()
    follow_status = IntegerField()
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
        for k in (set(user_dict) - set(cls._meta.fields)):
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


class Cache(BaseModel):
    id = BigIntegerField(primary_key=True)
    user = ForeignKeyField(User, backref="caches")
    from_timeline = JSONField(null=True)
    from_page = JSONField(null=True)

    @classmethod
    def from_id(cls, aweme_id: int, update=False):
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
            return parse_aweme(self.from_timeline)

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
        assert set(d1) == set(d2)
        for k in d1:
            if k in ['img_urls', 'video_url', 'aweme_from']:
                continue
            assert d1[k] == d2[k]


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
    region = TextField()
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
        for k in (set(aweme_dict) - set(cls._meta.fields)):
            unknown[k] = aweme_dict.pop(k)
        if unknown:
            console.log(
                f'find unknow fields: {unknown}', style='warning')
        assert 'unknown_fields' not in aweme_dict
        aweme_dict['unknown_fields'] = unknown or None

        if not (model := cls.get_or_none(cls.id == id)):
            aweme_dict['username'] = aweme_dict['nickname'].strip('-_')
            assert aweme_dict['username']
            cls.insert(aweme_dict).execute()
            return cls.get(id=id)
        model_dict = model_to_dict(model)
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
    [User, Post, Cache])
