import uuid
from datetime import datetime
from typing import List, Any

from pydantic import BaseModel
from sqlalchemy import Column, String, DateTime, Boolean, Result

from crud.rdb import Base, RDBClient


# class Model which inherits from Base
class User(Base):

    def __init__(
            self,
            user_id: str = uuid.uuid4().hex,
            email: str = 'xxx@email.com',
            username: str = 'xxx',
            department_name: str = 'xxx department'
    ):
        self.user_id = user_id
        self.email = email
        self.username = username
        self.department_name = department_name

    # noinspection SpellCheckingInspection
    __tablename__ = "user"

    user_id = Column(String(32), primary_key=True, comment="user_id, primary key")
    email = Column(String(64), comment="email")
    username = Column(String(32), comment="username")
    department_name = Column(String(32), comment="department name")
    created_at = Column(DateTime, default=datetime.now(), comment="created time")
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now(),
                        comment="last updated time")
    is_deleted = Column(Boolean(), default=False, comment="deleted flag, True is deleted, False is not deleted")

    def __repr__(self):
        return ('{"id": "%s", "email": "%s", "username": "%s", "department_name": "%s", "created_at": "%s", '
                '"updated_at": "%s", "is_deleted": "%s"}'
                % (self.id, self.email, self.username, self.department_name, self.created_at, self.updated_at,
                   self.is_deleted))


# class Mut Schema, which contains fields will be changed for update.
class UserMut(BaseModel):
    user_id: str
    email: str
    username: str
    department_name: str
    is_deleted: bool = False


# class Resource Schema, for loading data queried from the database
class UserResource(BaseModel):
    user_id: str
    email: str
    username: str
    department_name: str
    created_at: datetime
    updated_at: datetime
    is_deleted: bool


rdb_client = RDBClient(
    user='root',
    password='123456',
    host='127.0.0.1',
    port=3306,
    database='code_simplify'
)


# ================================= sample code =================================

def create_user():
    record = {
        'email': 'xxx@email.com',
        'username': 'xxx',
        'department_name': 'xxx department'
    }
    new_user: UserResource = rdb_client.create(
        model=User,
        obj_in=UserMut(**record),
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
    new_users: List[UserResource] = rdb_client.bulk_save(
        model=User,
        obj_in=[UserMut(**r) for r in record],
        primary_key_column_name='user_id',
        obj_out=UserResource
    )
    return new_users


def get_user():
    user_id = 'xxx'
    user: UserResource = rdb_client.get(
        model=User,
        primary_key_id=user_id,
        primary_key_column_name='user_id',
        obj_out=UserResource
    )
    return user


def list_users():
    users: List[UserResource] = rdb_client.list(
        model=User,
        obj_out=UserResource,
        conditions=UserMut(email='xxx@email.com')
    )
    return users


def get_paging_users():
    total, users = rdb_client.get_paging(
        model=User,
        obj_out=UserResource,
        conditions=UserMut(email='xxx@email.com', is_deleted=False),
        page=1,
        page_size=10,
        order_by_column_name='created_at',
        order_by_type='desc'
    )
    return total, users


def get_users_total_num():
    total = rdb_client.total(
        model=User,
        conditions=UserMut(is_deleted=False)
    )
    return total


def update_user():
    record = {
        'user_id': 'xxx',
        'email': 'xxx@email.com',
        'username': 'yyy',
        'department_name': 'yyy department'
    }
    new_user: UserResource = rdb_client.update(
        model=User,
        obj_in=UserMut(**record),
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
    res: Result[Any] = rdb_client.execute_sql('select * from user where id = 1')
    return res.all()


if __name__ == '__main__':
    create_user()
    bulk_save_users()
    get_user()
    list_users()
    get_paging_users()
    get_users_total_num()
    update_user()
    delete_user()
    phy_delete_user()
    execute_sql_sample()
