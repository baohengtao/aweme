from datetime import datetime
from pathlib import Path
from typing import Iterator, Self

import pendulum
from peewee import Model
from photosinfo.model import GirlSearch
from playhouse.postgres_ext import (
    ArrayField,
    BigIntegerField,
    BooleanField, CharField,
    DateTimeTZField,
    DoubleField,
    ForeignKeyField,
    IntegerField, JSONField,
    PostgresqlExtDatabase,
    TextField
)
from playhouse.shortcuts import model_to_dict, update_model_from_dict
from rich.prompt import Confirm

from aweme import console
from aweme.fetcher import download_files, fetcher
from aweme.page import Page
from aweme.post import get_aweme, parse_aweme
from aweme.user import get_user

database = PostgresqlExtDatabase("aweme", host="localhost")


class BaseModel(Model):
    class Meta:
        database = database

    def __repr__(self):
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
    location = CharField(null=True)
    ip = TextField(null=True)
    homepage = TextField()
    avatar = TextField()
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
    unknown_fields = JSONField(null=True)
    search_result = GirlSearch.get_search_results()['awe']
    redirect = BigIntegerField(null=True)

    @classmethod
    def from_id(cls, user_id: str | int, update=False) -> Self:
        if isinstance(user_id, int) or user_id.isdigit():
            model = cls.get_or_none(id=user_id)
        else:
            user_id = user_id.split('?')[0].split('/')[-1]
            model = cls.get_or_none(sec_uid=user_id)
        if model and not update:
            return model
        for _ in range(3):
            user_dict = get_user(user_id)
            if not model or user_dict['following'] == model.following:
                break
        else:
            console.log(model)
            if model.following and not Confirm.ask(
                    f'{model.username} unfollowed?'):
                raise ValueError
        if not model:
            if not user_dict['following']:
                console.log(f'{user_id} is not following', style='error')
                console.log(user_dict)
        return cls.upsert(user_dict)

    @classmethod
    def upsert(cls, user_dict: dict) -> Self:
        user_id = user_dict['id']
        unknown = {}
        for k in (set(user_dict) - set(cls._meta.columns)):
            unknown[k] = user_dict.pop(k)
        if unknown:
            console.log(
                f'find unknow fields: {unknown}', style='info')
        assert 'unknown_fields' not in user_dict
        user_dict['unknown_fields'] = unknown or None

        if not (model := cls.get_or_none(cls.id == user_id)):
            if 'username' not in user_dict:
                if username := cls.search_result.get(user_dict['sec_uid']):
                    user_dict['username'] = username
                else:
                    user_dict['username'] = user_dict['nickname'].strip('-_')
            assert user_dict['username']
            cls.insert(user_dict).execute()
            return cls.get_by_id(user_id)
        model_dict = model_to_dict(model)
        skiped_keys = {
            'follower_count', 'max_follower_count', 'aweme_count',
            'following_count', 'favoriting_count',
            'mplatform_followers_count', 'total_favorited',
            'unknown_fields',
        }
        for k, v in user_dict.items():
            assert v or v == 0 or k == 'unknown_fields'
            if k in skiped_keys:
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
    user = ForeignKeyField(User, backref="config", unique=True)
    username = CharField()
    nickname = CharField()
    following = BooleanField()
    aweme_count = IntegerField()
    aweme_fetch = BooleanField(default=True, null=True)
    aweme_fetch_at = DateTimeTZField(null=True)
    aweme_cache_at = DateTimeTZField(null=True)
    post_at = DateTimeTZField(null=True)
    post_cycle = IntegerField(null=True)
    aweme_next_fetch = DateTimeTZField(null=True)
    aweme_first_fetch = DateTimeTZField(null=True)
    signature = CharField(null=True)
    school_name = CharField(null=True)
    age = IntegerField(null=True)
    homepage = TextField()
    photos_num = IntegerField(default=0)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.page = Page(self.user_id)

    def __str__(slef):
        return super().__repr__()

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
            aweme = Cache.upsert(aweme).parse()
            aweme = Post.upsert(aweme)
            if (create_time := aweme.create_time) < since:
                if is_top:
                    console.log('skip top aweme')
                    continue
                else:
                    console.log(f'time {create_time:%y-%m-%d} is before '
                                f'{since:%y-%m-%d}, finished!')
                    break
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
        console.log(self.user)
        now, i = pendulum.now(), 0
        for i, aweme in enumerate(self.get_homepage(since=since), start=1):
            console.log(aweme, '\n')
        console.log(f'{i} awemes cached for {self.username}')
        self.aweme_cache_at = now
        self.post_at = self.user.posts.order_by(
            Post.create_time.desc()).first().create_time
        self.post_cycle = self.get_post_cycle()
        self.aweme_next_fetch = now.add(hours=self.post_cycle/2)
        self.save()

    def fetch_aweme(self, download_dir: Path):
        fetcher.toggle_alt(not self.following)
        if self.aweme_fetch is None:
            self._caching_aweme_for_new()
            return
        elif self.aweme_fetch is False:
            return
        if self.aweme_fetch_at:
            since = pendulum.instance(self.aweme_fetch_at)
            estimated_post = since.diff().in_hours() / self.post_cycle
            estimated_post = f'estimated_new_posts:{estimated_post:.2f}'
            msg = f' (fetch_at:{since:%y-%m-%d} {estimated_post})'
        else:
            msg = "(New user)"
        console.rule(f"fetching {self.username}'s homepage {msg}")
        console.log(self.user)
        console.log(f"Media Saving: {download_dir}")
        now = pendulum.now()
        imgs = self._save_aweme(download_dir)
        download_files(imgs)
        console.log(f"{self.username}抖音获取完毕！")
        if self.aweme_fetch_at is None:
            self.aweme_first_fetch = now
        self.aweme_fetch_at = now
        self.post_at = self.user.posts.order_by(
            Post.create_time.desc()).first().create_time
        self.post_cycle = self.get_post_cycle()
        self.aweme_next_fetch = now.add(hours=self.post_cycle)
        self.save()

    def get_post_cycle(self) -> int:
        interval = pendulum.Duration(days=30)
        if not (fetch_at := self.aweme_cache_at or self.aweme_fetch_at):
            return
        start, end = fetch_at-interval, fetch_at
        count = self.user.posts.where(
            Post.create_time.between(start, end)).count()
        cycle = interval / (count + 1)
        return cycle.in_hours()

    def _save_aweme(self, download_dir: Path) -> Iterator[dict]:
        user_root = 'User' if (
            self.photos_num and self.aweme_fetch_at) else 'NewInit'
        if self.aweme_fetch_at and user_root == 'NewInit':
            if not (download_dir / user_root / self.username).exists():
                user_root = 'New'
        img_dir = download_dir / user_root / self.username
        if user_root == 'NewInit':
            vid_dir = img_dir
        else:
            vid_dir = download_dir / 'mp4' / user_root
        since = self.aweme_fetch_at or pendulum.from_timestamp(0)
        console.log(f'fetching aweme from {since:%y-%m-%d}')
        aweme_ids = []
        for aweme in self.get_homepage(since):
            aweme_ids.append(aweme.id)
            console.log(aweme, '\n')
            save_path = vid_dir if aweme.is_video else img_dir
            medias = list(aweme.medias(save_path))
            console.log(f'Downloading {len(medias)} files to {download_dir}')
            yield from medias
        console.log(f'{len(aweme_ids)} awemes fetched')
        if self.aweme_fetch_at:
            return
        for cache in Cache.select().where(Cache.user_id == self.user_id):
            if not Post.get_or_none(id=cache.id):
                Post.upsert(cache.parse())
        if awemes := self.user.posts.where(Post.id.not_in(aweme_ids)):
            console.log(
                f'{len(awemes)} awemes not visible now but cached, saving...')
            for aweme in awemes:
                if aweme.username != self.username:
                    aweme.username = self.username
                    aweme.save()
                console.log(aweme, '\n')
                save_path = vid_dir if aweme.is_video else img_dir
                medias = list(aweme.medias(save_path))
                console.log(
                    f'Downloading {len(medias)} files to {download_dir}')
                yield from medias

    @classmethod
    def update_table(cls):
        from photosinfo.model import Girl

        for config in cls:
            config: cls
            if config.aweme_fetch is None:
                assert config.aweme_fetch_at is None
            elif config.aweme_fetch is True:
                assert not (config.aweme_cache_at and config.aweme_fetch_at)
            # else:
            #     assert config.aweme_fetch_at and not config.aweme_cache_at

            config.username = config.user.username
            if girl := Girl.get_or_none(username=config.username):
                config.photos_num = girl.awe_num
            else:
                config.photos_num = 0
            if fetch_at := (config.aweme_fetch_at or config.aweme_cache_at):
                config.post_cycle = config.get_post_cycle()
                config.aweme_next_fetch = fetch_at + \
                    pendulum.duration(hours=config.post_cycle)

            config.save()


class Artist(BaseModel):
    username = CharField(index=True)
    user = ForeignKeyField(User, unique=True, backref='artist')
    age = IntegerField(null=True)
    photos_num = IntegerField(default=0)
    aweme_count = IntegerField()
    signature = CharField(null=True)
    school_name = ArrayField(field_class=TextField, null=True)
    following_count = IntegerField()
    follower_count = IntegerField()
    homepage = CharField(null=True)

    _cache: dict[int, Self] = {}

    class Meta:
        table_name = "artist"

    @classmethod
    def from_id(cls, user_id: int, update: bool = False) -> Self:
        if not update and user_id in cls._cache:
            return cls._cache[user_id]
        user = User.from_id(user_id, update=update)
        user_dict = model_to_dict(user)
        user_dict['user_id'] = user_dict.pop('id')
        user_dict = {k: v for k, v in user_dict.items()
                     if k in cls._meta.columns}
        if cls.get_or_none(user_id=user_id):
            cls.update(user_dict).where(cls.user_id == user_id).execute()
        else:
            cls.insert(user_dict).execute()
        artist = cls.get(user_id=user_id)
        cls._cache[user_id] = artist
        return artist

    @property
    def xmp_info(self):
        xmp = {
            "Artist": self.username,
            "ImageCreatorID": self.homepage,
            "ImageSupplierID": self.user_id,
            "ImageSupplierName": "Aweme",
        }

        return {"XMP:" + k: v for k, v in xmp.items()}


class Cache(BaseModel):
    id = BigIntegerField(primary_key=True)
    user_id = BigIntegerField()
    from_timeline = JSONField(null=True)
    from_page = JSONField(null=True)
    blog_url = TextField()
    added_at = DateTimeTZField(null=True)
    updated_at = DateTimeTZField(null=True)

    @classmethod
    def from_id(cls, aweme_id: int, update=False) -> dict:
        if not update and (cache := cls.get_or_none(id=aweme_id)):
            return cache.parse()
        cache = get_aweme(aweme_id)
        cache = cls.upsert(cache)
        return cache.parse()

    def parse(self):
        self._check_parse()
        aweme = parse_aweme(self.from_page or self.from_timeline)
        assert 'updated_at' not in aweme
        assert 'added_at' not in aweme
        if self.updated_at:
            aweme['updated_at'] = self.updated_at
        if self.added_at:
            aweme['added_at'] = self.added_at
        return aweme

    def __repr__(self):
        return super().__repr__()

    @classmethod
    def upsert(cls, aweme: dict) -> Self:
        aweme_id, user_id = aweme['aweme_id'], aweme['author_user_id']
        if aweme['images']:
            blog_url = f'https://www.douyin.com/note/{aweme["aweme_id"]}'
        else:
            blog_url = f'https://www.douyin.com/video/{aweme["aweme_id"]}'
        row = dict(id=aweme_id, user_id=user_id, blog_url=blog_url)
        if aweme['aweme_from'] == 'page':
            row['from_page'] = aweme
        else:
            assert aweme['aweme_from'] == 'timeline'
            row['from_timeline'] = aweme
        if (cache := cls.get_or_none(id=aweme_id)):
            update_model_from_dict(cache, row)
            cache.updated_at = pendulum.now()
            cache.save()
        else:
            row['added_at'] = pendulum.now()
            cls.insert(row).execute()
        cache = cls.get_by_id(aweme_id)
        cache._check_parse()
        return cache

    def _check_parse(self):
        if not (self.from_page and self.from_timeline):
            return
        d1, d2 = parse_aweme(self.from_page), parse_aweme(self.from_timeline)
        common_key = set(d1) & set(d2)
        if set(d1) != set(d2):
            if x := (set(d2) - common_key):
                x = {k: d2[k] for k in x}
                console.log(
                    f'find unknow field from timeline: {x}',
                    style='error')
            if x := set(d1) - common_key:
                assert x == {'video_size', 'video_hash'}

        for k in common_key:
            if k in ['img_urls', 'video_url', 'aweme_from', 'digg_count']:
                continue
            if d1[k] != d2[k]:
                assert k in ['duration', 'bit_rate', 'height',
                             'width',]
                assert d1[k] > d2[k] or k in ['width', 'height']


class Post(BaseModel):
    id = BigIntegerField(primary_key=True)
    user = ForeignKeyField(User, backref="posts")
    sec_uid = TextField()
    username = CharField()
    nickname = CharField()
    create_time = DateTimeTZField()
    desc = TextField(null=True)
    blog_url = TextField()
    location = TextField(null=True)
    location_id = BigIntegerField(null=True)
    longitude = DoubleField(null=True)
    latitude = DoubleField(null=True)
    region = TextField(null=True)
    tags = ArrayField(CharField, null=True)
    at_users = ArrayField(CharField, null=True)
    video_tag = ArrayField(CharField, null=True)
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
    is_video = BooleanField()
    is_life_item = BooleanField()
    is_story = BooleanField()
    is_image_beat = BooleanField()
    is_multi_content = IntegerField(null=True)
    category_da = IntegerField(null=True)

    aweme_from = CharField()
    aweme_type = CharField()
    danmaku_cnt = IntegerField(null=True)
    original = IntegerField()
    preview_video_status = IntegerField()
    group_id = BigIntegerField()
    comment_gid = BigIntegerField()
    unknown_fields = JSONField(null=True)
    activity_video_type = IntegerField()
    added_at = DateTimeTZField(null=True)
    updated_at = DateTimeTZField(null=True)

    @classmethod
    def from_id(cls, aweme_id: int, update=False, ignore_unknow=True) -> Self:
        aweme_dict = Cache.from_id(aweme_id, update=update)
        return cls.upsert(aweme_dict, ignore_unknow)

    @classmethod
    def upsert(cls, aweme_dict: dict, ignore_unknow=False) -> Self:
        if address := aweme_dict.pop('address', None):
            loc_info = Location.upsert(address).info
            desc = aweme_dict.get('desc', '').strip()
            assert not desc.endswith('📍')
            desc += f' 📍{loc_info["location"]}'
            aweme_dict['desc'] = desc

            assert aweme_dict | loc_info == loc_info | aweme_dict
            aweme_dict |= loc_info
        id = aweme_dict['id']
        assert Cache.get_or_none(id=id)
        unknown = {}
        for k in (set(aweme_dict) - set(cls._meta.columns)):
            unknown[k] = aweme_dict.pop(k)
        if unknown and not ignore_unknow:
            console.log(
                f'find unknow fields: {unknown}', style='info')
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
            if (ori := model_dict[k]) == v or k in ['img_urls', 'video_url']:
                continue
            if k in ['collect_count', 'comment_count', 'digg_count', 'share_count']:
                continue
            if k == 'unknown_fields':
                continue
            if k == 'updated_at':
                assert not model_dict[k] or v > model_dict[k]
                continue
            console.log(f'+{k}: {v}', style='green bold on dark_green')
            if ori is not None:
                console.log(f'-{k}: {ori}', style='red bold on dark_red')
        cls.update(aweme_dict).where(cls.id == id).execute()
        return cls.get(id=id)

    def medias(self, filepath: Path = None) -> Iterator[dict]:
        prefix = f'{self.username}_{self.create_time:%y-%m-%d}_{self.id}'
        assert self.is_video == bool(
            self.video_url) == (not bool(self.img_urls))
        if self.is_video:
            assert self.video_hash
            yield {
                'url': self.video_url,
                'filename': f'{prefix}.mp4',
                'filepath': filepath,
                'xmp_info': self.gen_meta(url=self.video_url),
                'filesize': self.video_size,
                'hash': self.video_hash,
            }
            return
        assert len(self.img_ids) == len(self.img_urls)
        for sn, (img_id, url) in enumerate(
                zip(self.img_ids, self.img_urls), start=1):
            assert img_id in url
            if url == '':
                console.log(f'cannot get url of {sn}th img', style='error')
                continue
            yield {
                'url': url,
                'filename': f'{prefix}_{sn}.webp',
                'filepath': filepath,
                'xmp_info': self.gen_meta(sn=sn, url=url),
            }

    def gen_meta(self, sn: str | int = '', url: str = "") -> dict:
        if (pic_num := len(self.img_ids or [])) == 1:
            assert not sn or int(sn) == 1
            sn = ""
        elif sn and pic_num > 9:
            sn = f"{int(sn):02d}"
        xmp_info = {
            "ImageUniqueID": self.id,
            "ImageSupplierID": self.user_id,
            "ImageSupplierName": "Aweme",
            "ImageCreatorName": self.username,
            "BlogTitle":  f"{self.desc or ''}".strip(),
            "BlogURL": self.blog_url,
            "Location": self.location,
            "DateCreated": (self.create_time +
                            pendulum.Duration(microseconds=int(sn or 0))),
            "SeriesNumber": sn,
            "URLUrl": url,
        }

        xmp_info["DateCreated"] = xmp_info["DateCreated"].strftime(
            "%Y:%m:%d %H:%M:%S.%f").strip('0').strip('.')
        res = {"XMP:" + k: v for k, v in xmp_info.items() if v}
        if self.location:
            res['AwemeLocation'] = (self.latitude, self.longitude)
        return res

    def __repr__(self):
        return super().__repr__()

    def __str__(self):
        model = model_to_dict(self, recurse=False)
        res = {}
        skip_keys = ['is_image_beat', 'is_life_item',
                     'is_story', 'is_video',
                     'width', 'height',  'activity_video_type',
                     'group_id', 'comment_gid']
        for k, v in model.items():
            if v is None:
                continue
            if k in skip_keys:
                continue
            if k in ['admire_count', 'collect_count', 'comment_count',
                     'digg_count', 'play_count', 'share_count',
                     'user_digged', 'collect_stat']:
                if v == 0:
                    continue
            if k in ['img_urls']:
                continue
            res[k] = v
        return "\n".join(f'{k}: {v}' for k, v in res.items())


class Location(BaseModel):
    id = BigIntegerField(BigIntegerField)
    address = CharField(null=True)
    simple_addr = CharField(null=True)
    province = CharField(null=True)
    city = CharField(null=True)
    district = CharField(null=True)
    country = CharField()
    country_code = CharField()
    city_code = IntegerField(null=True)
    ad_code_v2 = IntegerField(null=True)
    city_code_v2 = IntegerField(null=True)
    location_name = CharField()
    location_prefix = CharField(null=True)
    longitude = DoubleField()
    latitude = DoubleField()

    @classmethod
    def upsert(cls, address: dict):
        address = {k: v for k, v in address.items() if v not in ['', None]}
        for k in ['id', 'city_code', 'ad_code_v2', 'city_code_v2']:
            if k in address:
                address[k] = int(address[k])

        if not cls.get_or_none(id=address['id']):
            cls.insert(address).execute()
            return cls.get(id=address['id'])

        cls.update(address).where(cls.id == address['id']).execute()
        return cls.get(id=address['id'])

    @property
    def info(self):
        if self.location_prefix:
            location = f'{self.location_prefix}·{self.location_name}'
        else:
            location = self.location_name
        return {
            'location': location,
            'location_id': self.id,
            'longitude': self.longitude,
            'latitude': self.latitude,
        }


database.create_tables(
    [User, UserConfig, Artist, Post, Cache, Location])
