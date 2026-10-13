import builtins
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol, cast, overload

from pydantic import BaseModel
from sqlalchemy import Result, create_engine, inspect, text
from sqlalchemy.engine import URL, CursorResult, make_url
from sqlalchemy.orm import DeclarativeBase, Session, scoped_session, sessionmaker
from sqlalchemy.pool import Pool, QueuePool


class RDBBase(DeclarativeBase):
    pass


class _PoolDialect(Protocol):
    @classmethod
    def get_pool_class(cls, url: URL) -> type[Pool]: ...


class RDBClient[
    ModelType: RDBBase,
    SchemaMutType: BaseModel,
    SchemaResourceType: BaseModel,
]:
    """Synchronous CRUD for SQLAlchemy models with a single primary key.

    Methods create and close their own session unless ``db`` is supplied.
    Pass ``db`` and ``auto_commit=False`` to compose writes in one transaction.
    """

    def __init__(
            self,
            user: str | None = None,
            password: str | None = None,
            host: str | None = None,
            port: int | None = None,
            database: str | None = None,
            db_type: str = 'mysql+pymysql',
            max_overflow: int = 10,  # 增加到10
            pool_size: int = 20,     # 减小到20，避免过多连接
            pool_timeout: int = 30,   # 减小超时时间
            pool_recycle: int = 3600, # 增加到1小时，避免连接被数据库断开
            echo: bool = False,
            *,
            url: str | URL | None = None,
            **kwargs: Any,
    ) -> None:
        """Accept a SQLAlchemy URL or connection components.

        QueuePool settings are applied only to compatible pools. Other engine
        options, such as ``connect_args`` and ``poolclass``, pass through.
        """
        if url is not None:
            engine_url = make_url(url)
        elif db_type.split('+', 1)[0] == 'sqlite':
            engine_url = URL.create(db_type, database=database)
        else:
            engine_url = URL.create(
                db_type, username=user, password=password, host=host,
                port=port, database=database,
            )
        engine_options: dict[str, Any] = dict(kwargs, echo=echo)
        if kwargs.get('pool') is None:
            engine_options.setdefault('pool_pre_ping', True)
            engine_options['pool_recycle'] = pool_recycle
            pool_class = kwargs.get('poolclass')
            if pool_class is None:
                # Concrete SQLAlchemy dialects provide this class-level pool API.
                dialect_class = cast(type[_PoolDialect], engine_url.get_dialect())
                pool_class = dialect_class.get_pool_class(engine_url)
            if issubclass(pool_class, QueuePool):
                engine_options.update(
                    max_overflow=max_overflow, pool_size=pool_size,
                    pool_timeout=pool_timeout,
                )
        self.engine = create_engine(engine_url, **engine_options)
        self.session = scoped_session(sessionmaker(bind=self.engine, expire_on_commit=False))

    @contextmanager
    def _session_scope(
            self, db: Session | None = None, *, write: bool = False,
            auto_commit: bool = True,
    ) -> Iterator[Session]:
        if write and not auto_commit and db is None:
            raise ValueError('auto_commit=False requires an explicit db session')
        owns_session = db is None
        # A standalone operation must not reuse a caller's thread-local session.
        session = db if db is not None else self.session.session_factory()
        try:
            yield session
            if write:
                if auto_commit:
                    session.commit()
                else:
                    session.flush()
        except Exception:
            if owns_session or (write and auto_commit):
                session.rollback()
            raise
        finally:
            if owns_session:
                session.close()

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Commit a group of operations on success and roll back on failure.

        Supply the yielded session as ``db`` and set ``auto_commit=False`` on
        each write. The session is closed when this context exits.
        """
        with self._session_scope(write=True) as db:
            yield db

    @staticmethod
    def _column(model: type[ModelType], name: str):
        if name not in inspect(model).column_attrs:
            raise ValueError(f'Unknown column {name!r} on {model.__name__}')
        return getattr(model, name)

    @staticmethod
    def _input_data(obj: BaseModel | dict[str, Any], *, exclude_unset: bool = False) -> dict[str, Any]:
        if isinstance(obj, BaseModel):
            return obj.model_dump(exclude_unset=exclude_unset)
        return dict(obj)

    def _filters(
            self, model: type[ModelType], conditions: BaseModel | dict[str, Any] | None = None,
            deleted_status_column_name: str | None = 'is_deleted', range_all: bool = False,
    ) -> list:
        data = self._input_data(conditions, exclude_unset=True) if conditions is not None else {}
        filters = [self._column(model, name) == value for name, value in data.items()]
        if deleted_status_column_name and not range_all:
            columns = inspect(model).column_attrs
            # Plain tables need no soft-delete field; misspelled custom fields fail.
            if deleted_status_column_name in columns or deleted_status_column_name != 'is_deleted':
                filters.append(self._column(model, deleted_status_column_name).is_(False))
        return filters

    @staticmethod
    @overload
    def _output(
            data: ModelType, obj_out: type[SchemaResourceType] | None,
    ) -> SchemaResourceType | ModelType: ...

    @staticmethod
    @overload
    def _output(
            data: ModelType | None, obj_out: type[SchemaResourceType] | None,
    ) -> SchemaResourceType | ModelType | None: ...

    @staticmethod
    def _output(
            data: ModelType | None, obj_out: type[SchemaResourceType] | None,
    ) -> SchemaResourceType | ModelType | None:
        if data is None:
            return None
        if obj_out is not None:
            return obj_out.model_validate(data, from_attributes=True)
        # Load scalar defaults before an owned session detaches the model.
        for attribute in inspect(data).mapper.column_attrs:
            getattr(data, attribute.key)
        return data

    def _new_object(
            self, model: type[ModelType], obj_in: BaseModel | dict[str, Any],
            primary_key_column_name: str,
    ) -> ModelType:
        data = self._input_data(obj_in)
        column = self._column(model, primary_key_column_name).property.columns[0]
        if data.get(primary_key_column_name) is None:
            data.pop(primary_key_column_name, None)
        obj = model(**data)
        if getattr(obj, primary_key_column_name) is None and column.default is None and column.server_default is None:
            try:
                key_type = column.type.python_type
            except NotImplementedError:
                key_type = None
            if key_type is str:
                setattr(obj, primary_key_column_name, uuid.uuid4().hex)
            elif key_type is uuid.UUID:
                setattr(obj, primary_key_column_name, uuid.uuid4())
        return obj

    def get(
            self,
            model: type[ModelType],
            primary_key_id: int | str | uuid.UUID,
            db: Session | None = None,
            primary_key_column_name: str = 'id',
            obj_out: type[SchemaResourceType] | None = None,
            deleted_status_column_name: str | None = 'is_deleted',
            range_all: bool = False
    ) -> SchemaResourceType | ModelType | None:
        """Get a record or None; ``range_all=True`` includes deleted records."""
        filters = [self._column(model, primary_key_column_name) == primary_key_id]
        filters.extend(self._filters(model, deleted_status_column_name=deleted_status_column_name, range_all=range_all))
        with self._session_scope(db) as session:
            data = session.query(model).filter(*filters).first()
            return self._output(data, obj_out)

    def list(
            self,
            model: type[ModelType],
            db: Session | None = None,
            deleted_status_column_name: str | None = 'is_deleted',
            range_all: bool = False,
            obj_out: type[SchemaResourceType] | None = None,
            conditions: BaseModel | dict[str, Any] | None = None
    ) -> list[SchemaResourceType | ModelType]:
        """List matching records, excluding soft-deleted records by default.

        Conditions use explicitly supplied schema fields or dictionary keys.
        Values such as False, 0, an empty string and None are valid filters.
        """
        filters = self._filters(model, conditions, deleted_status_column_name, range_all)
        with self._session_scope(db) as session:
            data = session.query(model).filter(*filters).all()
            return [self._output(obj, obj_out) for obj in data]

    def get_paging(
            self,
            model: type[ModelType],
            db: Session | None = None,
            page: int = 1,
            page_size: int = 20,
            order_by_type: str = 'desc',
            order_by_column_name: str = 'id',
            conditions: BaseModel | dict[str, Any] | None = None,
            obj_out: type[SchemaResourceType] | None = None,
            deleted_status_column_name: str | None = 'is_deleted',
            range_all: bool = False,
    ) -> tuple[int, builtins.list[ModelType | SchemaResourceType]]:
        """Return a filtered total and a page of the same query (page starts at 1)."""
        if type(page) is not int or page < 1:
            raise ValueError('page must be a positive integer')
        if type(page_size) is not int or page_size < 1:
            raise ValueError('page_size must be a positive integer')
        if order_by_type not in ('asc', 'desc'):
            raise ValueError('order_by_type must be asc or desc')
        column = self._column(model, order_by_column_name)
        ordering = column.desc() if order_by_type == 'desc' else column.asc()
        filters = self._filters(model, conditions, deleted_status_column_name, range_all)
        with self._session_scope(db) as session:
            query = session.query(model).filter(*filters)
            total = query.count()
            if total == 0:
                return 0, []
            data = query.order_by(ordering).offset(page_size * (page - 1)).limit(page_size).all()
            return total, [self._output(obj, obj_out) for obj in data]

    def total(
            self,
            model: type[ModelType],
            db: Session | None = None,
            conditions: BaseModel | dict[str, Any] | None = None,
            deleted_status_column_name: str | None = 'is_deleted',
            range_all: bool = False,
    ) -> int:
        """Count records using the same filters and deletion range as list/paging."""
        filters = self._filters(model, conditions, deleted_status_column_name, range_all)
        with self._session_scope(db) as session:
            return session.query(model).filter(*filters).count()

    def bulk_save(
            self,
            model: type[ModelType],
            obj_in: builtins.list[SchemaMutType],
            db: Session | None = None,
            obj_out: type[SchemaResourceType] | None = None,
            primary_key_column_name: str = 'id',
            auto_commit: bool = True
    ) -> builtins.list[SchemaResourceType | ModelType]:
        """Insert records atomically and return populated keys and scalar defaults."""
        with self._session_scope(db, write=True, auto_commit=auto_commit) as session:
            objects = [self._new_object(model, obj, primary_key_column_name) for obj in obj_in]
            session.add_all(objects)
            session.flush()
            return [self._output(obj, obj_out) for obj in objects]

    def create(
            self,
            model: type[ModelType],
            obj_in: SchemaMutType,
            db: Session | None = None,
            obj_out: type[SchemaResourceType] | None = None,
            primary_key_column_name: str = 'id',
            auto_commit: bool = True
    ) -> SchemaResourceType | ModelType:
        """Insert a record, honoring database defaults and integer autoincrement.

        String keys without a default retain the UUID hex fallback. Output
        validation happens before a managed transaction is committed.
        """
        with self._session_scope(db, write=True, auto_commit=auto_commit) as session:
            obj = self._new_object(model, obj_in, primary_key_column_name)
            session.add(obj)
            session.flush()
            session.refresh(obj)
            return self._output(obj, obj_out)

    def update(
            self,
            model: type[ModelType],
            obj_in: SchemaMutType | dict[str, Any],
            db: Session | None = None,
            primary_key_id: int | str | uuid.UUID | None = None,
            primary_key_column_name: str = 'id',
            db_obj: ModelType | None = None,
            obj_out: type[SchemaResourceType] | None = None,
            auto_commit: bool = True
    ) -> SchemaResourceType | ModelType | None:
        """Update supplied fields and return the actual row, or None if absent.

        An ID can come from the argument, input or db_obj. Conflicting IDs are
        rejected. Unset schema fields are preserved; explicit None writes NULL.
        """
        data = self._input_data(obj_in, exclude_unset=True)
        key_column = self._column(model, primary_key_column_name)
        for field in data:
            self._column(model, field)
        input_id = data.pop(primary_key_column_name, None)
        if primary_key_id is not None and input_id is not None and primary_key_id != input_id:
            raise ValueError('primary_key_id conflicts with the input primary key')
        key = primary_key_id if primary_key_id is not None else input_id
        if db_obj is not None:
            if not isinstance(db_obj, model):
                raise ValueError('db_obj must be an instance of model')
            object_id = getattr(db_obj, primary_key_column_name)
            if key is None:
                key = object_id
            elif key != object_id:
                raise ValueError('The primary key conflicts with db_obj')
        if key is None:
            raise ValueError('Neither obj_in, primary_key_id nor db_obj provides a primary key')
        with self._session_scope(db, write=True, auto_commit=auto_commit) as session:
            obj = session.query(model).filter(key_column == key).first()
            if obj is None:
                return None
            for field, value in data.items():
                setattr(obj, field, value)
            session.flush()
            session.refresh(obj)
            return self._output(obj, obj_out)

    def delete(
            self,
            model: type[ModelType],
            primary_key_ids: int | str | uuid.UUID | builtins.list[int] | builtins.list[str] | builtins.list[uuid.UUID],
            db: Session | None = None,
            primary_key_column_name: str = 'id',
            deleted_status_column_name: str = 'is_deleted',
            auto_commit: bool = True
    ):
        """Soft-delete one or more records; a mapped deletion column is required."""
        key_column = self._column(model, primary_key_column_name)
        deleted_column = self._column(model, deleted_status_column_name)
        condition = key_column.in_(primary_key_ids) if isinstance(primary_key_ids, list) else key_column == primary_key_ids
        with self._session_scope(db, write=True, auto_commit=auto_commit) as session:
            session.query(model).filter(condition).update({deleted_column: True})

    def physical_delete(
            self,
            model: type[ModelType],
            primary_key_id: int | str | uuid.UUID,
            db: Session | None = None,
            primary_key_column_name: str = 'id',
            auto_commit: bool = True
    ):
        """Delete a record, retaining ORM cascade behavior."""
        key_column = self._column(model, primary_key_column_name)
        with self._session_scope(db, write=True, auto_commit=auto_commit) as session:
            obj = session.query(model).filter(key_column == primary_key_id).first()
            if obj is not None:
                session.delete(obj)

    def execute_sql(
            self,
            sql: str,
            db: Session | None = None,
            auto_commit: bool = True,
            params: dict[str, Any] | builtins.list[dict[str, Any]] | None = None,
    ) -> Result[Any]:
        """Execute SQL with named bind parameters (e.g. ``WHERE id=:id``).

        Owned row results are buffered before commit/close. Pass an explicit db
        and auto_commit=False to consume large results within your transaction.
        Non-row results retain SQLAlchemy's rowcount/lastrowid metadata.
        """
        with self._session_scope(db, write=True, auto_commit=auto_commit) as session:
            result = session.execute(text(sql), params if params is not None else {})
            if db is None and isinstance(result, CursorResult) and result.returns_rows:
                try:
                    return result.freeze()()
                finally:
                    result.close()
            return result
