# code-simplify
A python tool library that covers a wide range of common tools to simplify your work and reduce repetitive code.


# What is in it
* `http utils` based on `aiohttp`, including `SSE HANDLER`, `HEAD`, `GET`, `POST`, `OPTIONS`, `PUT`, `PATCH`, `DELETE`.
* `logger template` based on logging in std.
* `common crud` based on SQLAlchemy, including `GET`, `LIST`, `CREATE`, `BULK SAVE`, `UPDATE`, `TOTAL`, `GET PAGING`, `DELETE`, `PHYSICAL DELETE`, `EXECUTE SQL`


# How to use
just see [examples](https://github.com/Yaocool/code-simplify/tree/main/examples) package.


## Database client

Requires Python 3.12+, aiohttp 3.14.5+, Pydantic 2.14.1+ and SQLAlchemy 2.1.4+.
Install the driver for your
database: `pip install 'code-simplify[mysql]'` for the default `mysql+pymysql`, or
`pip install 'code-simplify[postgresql]'` for `postgresql+psycopg`. SQLite needs
no additional driver.

```python
from code_simplify.crud.rdb import RDBBase, RDBClient

client = RDBClient(url="sqlite:///example.db")
# Other SQLAlchemy dialects can use their own URL, or connection components:
# client = RDBClient(user="app", password="p@ss:/?#", host="localhost",
#                    port=3306, database="app", db_type="mysql+pymysql")

# Define your SQLAlchemy models before creating tables.
RDBBase.metadata.create_all(client.engine)
```

See [the runnable CRUD example](examples/crud.py) for models and schemas. Run it
with `python -m examples.crud`; it uses SQLite without external credentials.

The client wraps synchronous ORM CRUD for models with a single primary key.
Conditions accept a Pydantic schema or a dictionary and use equality comparisons.
Only explicitly set schema fields become filters: `False`, `0` and `""` remain
valid values, and an explicit `None` means `IS NULL`. Unknown filter/update columns
raise `ValueError`. Updates also use only explicitly set fields, so omitted schema
defaults do not overwrite stored values.

`get`, `list`, `get_paging` and `total` exclude `is_deleted=True` by default when
that column exists. Use `range_all=True` to include every record, or combine it
with `conditions={"is_deleted": True}` to list only deleted records. Set
`deleted_status_column_name` for a custom flag, or `None` to disable filtering.
Soft deletion requires a mapped flag column; tables without it can use
`physical_delete`. Pagination validates positive integer page/page_size values,
uses mapped columns for sorting and counts the same filtered query as the page.

`get` and `update` return `None` when a row is absent, including when `obj_out`
is supplied. `obj_out` uses Pydantic's ORM attribute validation. Inserts respect
integer autoincrement and model/database key defaults; string keys without a
default get a UUID hex value, and native UUID keys get a `uuid.UUID`. Bulk inserts
return populated keys and defaults through the normal ORM unit of work.

Each independent call creates and closes its own session, including on exceptions
and output validation errors. Returned ORM objects are detached with scalar fields
loaded. Pass an explicit `db` to retain the session and access lazy relationships.
The thread-local `client.session()` remains available for caller-managed sessions;
independent calls use separate sessions and never reuse or close that registry entry.
Caller-owned sessions must be closed by the caller (`client.session.remove()` for
the thread-local registry).

Writes with `auto_commit=True` commit on success and roll back on failure, including
when an explicit `db` is passed. With `auto_commit=False`, the caller must supply
`db` and owns commit/rollback, including after an exception. Successful writes are
flushed but remain uncommitted. Use one transaction for several operations:

```python
with client.transaction() as db:
    # User/UserMut are the models defined in examples/crud.py.
    user = client.create(
        User, UserMut(email="app@example.com", username="app", department_name="dev"),
        primary_key_column_name="user_id", db=db, auto_commit=False,
    )
    client.update(
        User, {"username": "new-name"}, primary_key_id=user.user_id,
        primary_key_column_name="user_id", db=db, auto_commit=False,
    )
# Commits all operations, or rolls them back and closes on error.
```

Raw SQL accepts named bind parameters; keep the SQL template trusted and bind
user-provided values through `params`:

```python
rows = client.execute_sql(
    "SELECT * FROM user WHERE username = :name", params={"name": "app"},
).mappings().all()
```

Row results from independent calls are buffered before the connection is released.
Non-row results retain `rowcount`/`lastrowid`. For large queries, pass `db` with
`auto_commit=False` and consume the SQLAlchemy result inside your session. QueuePool
settings apply only to compatible pools; SQLite in-memory and custom StaticPool or
NullPool configurations omit unsupported queue options. `pool_pre_ping=True` is
enabled by default and can be overridden through engine options. Call
`client.engine.dispose()` when the client is no longer needed.

### 数据库接口的行为调整

- 项目要求 Python 3.12 及以上；运行依赖已升级至 aiohttp 3.14.5、Pydantic 2.14.1 和 SQLAlchemy 2.1.4。
- 默认查询仅包含未软删除的数据；`range_all=True` 表示包含全部数据。分页与总数使用相同的筛选规则。
- 筛选保留显式传入的 `False`、`0`、空字符串和 `None`；没有传入的 Pydantic 字段不参与筛选或更新。
- 传入的 Session 由调用方关闭。`auto_commit=False` 必须同时传入 `db`，并由调用方统一提交或回滚。
- 更新可从参数、输入字段或 `db_obj` 获取主键；主键冲突会报错，不存在的记录返回 `None`。
- 原来依赖分页/计数包含软删除记录的调用，需要显式传入 `range_all=True`。只查询已删除记录可同时传入 `conditions={"is_deleted": True}`。

### Local verification

```shell
pip install -e '.[mysql,dev]'
python -m ruff check .
python -m pyright
python -m pytest -q -W error
python -m examples.crud
```

Ruff and Pyright use the project's Python 3.12 minimum. Pyright also uses the
local `.venv` so its dependency resolution matches the editor.

The regression suite executes against SQLite and checks results, transaction
visibility, rollback and connection cleanup. MySQL/PostgreSQL servers are not
required by this suite; real driver/server integration should be verified in the
target environment before deployment.


# How to install

## PyPI (recommend)
```shell script
$ pip install code-simplify
```


## Local compilation
```shell script
$ git clone git@github.com:Yaocool/code-simplify.git
$ pip install -e '.[dev]'
$ python -m build
$ pip install ./dist/code_simplify-*-py3-none-any.whl
```


# Contributors Wall
<a href="https://github.com/Yaocool/code-simplify/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Yaocool/code-simplify&max=200" />
</a >
