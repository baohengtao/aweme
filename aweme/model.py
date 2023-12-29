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
    username = CharField(unique=True)
    nickname = CharField()
    signature = CharField()
    school_name = CharField()
    age = IntegerField()
    gender = IntegerField()
    following_count = IntegerField()
    follower_count = IntegerField()
    max_follower_count = IntegerField()
    aweme_count = IntegerField()
    forward_count = IntegerField()
    favoriting_count = IntegerField()
    total_favorited = IntegerField()
    show_favorite_list = BooleanField()
    city = CharField(null=True)
    district = CharField(null=True)
    ip = TextField()
    country = CharField()
    iso_country_code = CharField()
    homepage = TextField()
    avatar = TextField()
    signature_language = CharField()
    im_primary_role_id = IntegerField()
    im_role_ids = ArrayField(IntegerField)
    publish_landing_tab = IntegerField()

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
        if not (model := cls.get_or_none(cls.id == user_id)):
            user_dict['username'] = user_dict['nickname'].strip('-_')
            assert user_dict['username']
            cls.insert(user_dict).execute()
            return cls.get_by_id(user_id)
        model_dict = model_to_dict(model)
        for k, v in user_dict.items():
            assert v or v == 0
            if v == model_dict[k]:
                continue
            console.log(f'+{k}: {v}', style='green bold on dark_green')
            if (ori := model_dict[k]) is not None:
                console.log(f'-{k}: {ori}', style='red bold on dark_red')
        cls.update(user_dict).where(cls.id == user_id).execute()
        return cls.get_by_id(user_id)


database.create_tables(
    [User])
