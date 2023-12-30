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
from playhouse.shortcuts import model_to_dict

from aweme import console
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


database.create_tables(
    [User])
