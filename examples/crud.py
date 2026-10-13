import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Result, String

from code_simplify.crud.rdb import RDBBase, RDBClient


# class Model which inherits from Base
class User(RDBBase):
    # noinspection SpellCheckingInspection
    __tablename__ = "user"

    user_id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex, comment="user_id, primary key")
    email = Column(String(64), comment="email")
    username = Column(String(32), comment="username")
    department_name = Column(String(32), comment="department name")
    created_at = Column(DateTime, default=datetime.now, comment="created time")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now,
                        comment="last updated time")
    is_deleted = Column(Boolean(), default=False, comment="deleted flag, True is deleted, False is not deleted")

    def __repr__(self):
        return f'User(user_id={self.user_id!r}, username={self.username!r})'


# class Mut Schema, which contains fields will be changed for update.
class UserMut(BaseModel):
    user_id: str | None = None
    email: str
    username: str
    department_name: str
    is_deleted: bool = False


class UserFilter(BaseModel):
    email: str | None = None
    is_deleted: bool | None = None


# class Resource Schema, for loading data queried from the database
class UserResource(BaseModel):
    user_id: str
    email: str
    username: str
    department_name: str
    created_at: datetime
    updated_at: datetime
    is_deleted: bool


# SQLite makes this example runnable without a database server or credentials.
rdb_client = RDBClient[User, UserMut, UserResource](url='sqlite:///:memory:')


# ================================= sample code =================================

def create_user():
    record = {
        'email': 'xxx@email.com',
        'username': 'xxx',
        'department_name': 'xxx department'
    }
    new_user = rdb_client.create(
        model=User,
        obj_in=UserMut.model_validate(record),
        # the primary key column name is user_id not id, must set primary_key_column_name here
        primary_key_column_name='user_id',
        obj_out=UserResource
    )
    print('new user id: ', new_user.user_id)
    return new_user


def bulk_save_users():
    record = [
        {
            'user_id': 'xxx',
            'email': 'xxx@email.com',
            'username': 'xxx',
            'department_name': 'xxx department'
        },
        {
            'user_id': 'yyy',
            'email': 'yyy@email.com',
            'username': 'yyy',
            'department_name': 'yyy department'
        }
    ]
    new_users = rdb_client.bulk_save(
        model=User,
        obj_in=[UserMut.model_validate(r) for r in record],
        primary_key_column_name='user_id',
        obj_out=UserResource
    )
    return new_users


def get_user():
    user_id = 'xxx'
    user = rdb_client.get(
        model=User,
        primary_key_id=user_id,
        primary_key_column_name='user_id',
        obj_out=UserResource
    )
    return user


def list_users():
    users = rdb_client.list(
        model=User,
        obj_out=UserResource,
        conditions=UserFilter(email='xxx@email.com')
    )
    return users


def get_paging_users():
    total, users = rdb_client.get_paging(
        model=User,
        obj_out=UserResource,
        conditions=UserFilter(email='xxx@email.com', is_deleted=False),
        page=1,
        page_size=10,
        order_by_column_name='created_at',
        order_by_type='desc'
    )
    return total, users


def get_users_total_num():
    total = rdb_client.total(
        model=User,
        conditions=UserFilter(is_deleted=False)
    )
    return total


def update_user():
    record = {
        'user_id': 'xxx',
        'email': 'xxx@email.com',
        'username': 'yyy',
        'department_name': 'yyy department'
    }
    new_user = rdb_client.update(
        model=User,
        obj_in=UserMut.model_validate(record),
        # primary_key_id='xxx', # UserMut already has primary_key_id
        # the primary key column name is user_id not id, must set primary_key_column_name here
        primary_key_column_name='user_id',
        obj_out=UserResource
    )
    return new_user


def delete_user():
    user_id = 'xxx'
    rdb_client.delete(
        model=User,
        primary_key_ids=user_id,
        primary_key_column_name='user_id',
        # deleted_status_column_name='is_deleted'  # user table has is_deleted column
    )


def phy_delete_user():
    user_id = 'xxx'
    rdb_client.physical_delete(
        model=User,
        primary_key_id=user_id,
        primary_key_column_name='user_id',
    )


def execute_sql_sample():
    res: Result[Any] = rdb_client.execute_sql(
        'SELECT * FROM user WHERE username = :username',
        params={'username': 'xxx'},
    )
    return res.all()


if __name__ == '__main__':
    RDBBase.metadata.create_all(rdb_client.engine)
    try:
        create_user()
        bulk_save_users()
        get_user()
        list_users()
        get_paging_users()
        get_users_total_num()
        update_user()
        delete_user()
        phy_delete_user()
        print('SQL result:', execute_sql_sample())
    finally:
        rdb_client.session.remove()
        rdb_client.engine.dispose()
