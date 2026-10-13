import uuid
from datetime import datetime
from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Uuid,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from code_simplify.crud import rdb
from code_simplify.crud.rdb import RDBBase, RDBClient


class Record(RDBBase):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class PlainRecord(RDBBase):
    __tablename__ = "plain_records"

    key = Column(String(32), primary_key=True)
    name = Column(String, nullable=False)


class DefaultKeyRecord(RDBBase):
    __tablename__ = "default_key_records"

    id = Column(String, primary_key=True, default=lambda: "database-default")


class UUIDRecord(RDBBase):
    __tablename__ = "uuid_records"

    id = Column(Uuid, primary_key=True)
    name = Column(String, server_default=text("'server-default'"))


class CustomDeleteRecord(RDBBase):
    __tablename__ = "custom_delete_records"

    id = Column(Integer, primary_key=True)
    deleted = Column(Boolean, default=False, nullable=False)


class EmptyCreate(BaseModel):
    pass


class RecordCreate(BaseModel):
    name: str
    id: int | None = None
    score: int = 0
    enabled: bool = False
    note: str | None = None


class RecordFilter(BaseModel):
    name: str | None = None
    score: int | None = None
    enabled: bool | None = None
    note: str | None = None


class RecordPatch(BaseModel):
    name: str | None = None
    score: int | None = None
    enabled: bool = True
    note: str | None = None


class RecordResource(BaseModel):
    id: int
    name: str
    score: int
    enabled: bool
    note: str | None
    created_at: datetime


class InvalidResource(BaseModel):
    missing: str


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Inject a real SQLite engine so regressions can also run against the old constructor.
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    RDBBase.metadata.create_all(engine)
    monkeypatch.setattr(rdb, "create_engine", lambda *args, **kwargs: engine)
    client = RDBClient("user", "password", "localhost", 3306, "test")
    with Session(engine) as db:
        db.add_all([
            Record(id=1, name="zero", score=0, enabled=False, note=""),
            Record(id=2, name="one", score=1, enabled=True, note="filled"),
            Record(id=3, name="null", score=0, enabled=False, note=None),
            Record(id=4, name="deleted", score=0, enabled=False, is_deleted=True),
        ])
        db.commit()
    yield client, engine
    client.session.remove()
    engine.dispose()


@pytest.mark.parametrize("conditions, expected", [
    (RecordFilter(score=0), [1, 3]),
    (RecordFilter(enabled=False), [1, 3]),
    (RecordFilter(note=""), [1]),
    (RecordFilter(note=None), [3]),
    (RecordFilter(), [1, 2, 3]),
])
def test_list_preserves_explicit_filter_values(client, conditions, expected):
    rdb_client, _ = client
    assert sorted(row.id for row in rdb_client.list(Record, conditions=conditions)) == expected


def test_soft_delete_range_is_consistent(client):
    rdb_client, _ = client
    assert rdb_client.get(Record, 4) is None
    assert rdb_client.get(Record, 1, range_all=True).id == 1
    assert rdb_client.get(Record, 4, range_all=True).id == 4
    assert sorted(row.id for row in rdb_client.list(Record, range_all=True)) == [1, 2, 3, 4]
    assert rdb_client.total(Record) == 3
    assert rdb_client.total(Record, range_all=True) == 4


def test_paging_filters_before_count_and_limit(client):
    rdb_client, _ = client
    total, rows = rdb_client.get_paging(Record, conditions=RecordFilter(score=0), page_size=1)
    assert total == 2
    assert [row.id for row in rows] == [3]
    total, rows = rdb_client.get_paging(Record, conditions=RecordFilter(score=0), page=2, page_size=1)
    assert total == 2
    assert [row.id for row in rows] == [1]
    total, rows = rdb_client.get_paging(Record, conditions=RecordFilter(score=0), order_by_type="asc")
    assert total == 2
    assert [row.id for row in rows] == [1, 3]
    assert rdb_client.total(Record, conditions=RecordFilter(score=0)) == 2


@pytest.mark.parametrize("options", [
    {"page": 0}, {"page": -1}, {"page_size": 0}, {"page_size": -1},
    {"page": 1.5}, {"page": True}, {"order_by_type": "invalid"},
    {"order_by_column_name": "missing"},
])
def test_paging_rejects_invalid_options(client, options):
    rdb_client, engine = client
    with pytest.raises(ValueError):
        rdb_client.get_paging(Record, **options)
    assert engine.pool.checkedout() == 0


def test_get_serializes_orm_and_handles_missing_record(client):
    rdb_client, engine = client
    assert rdb_client.get(Record, 1, obj_out=RecordResource).name == "zero"
    assert rdb_client.get(Record, 999, obj_out=RecordResource) is None
    assert engine.pool.checkedout() == 0


@pytest.mark.parametrize("operation", ["get", "list", "paging", "empty_paging", "total"])
def test_read_paths_release_owned_sessions(client, operation):
    rdb_client, engine = client
    if operation == "get":
        rdb_client.get(Record, 1, obj_out=RecordResource)
    elif operation == "list":
        rdb_client.list(Record, obj_out=RecordResource)
    elif operation == "paging":
        rdb_client.get_paging(Record, obj_out=RecordResource, order_by_type="asc")
    elif operation == "empty_paging":
        rdb_client.get_paging(Record, conditions=RecordFilter(name="missing"))
    else:
        rdb_client.total(Record)
    assert engine.pool.checkedout() == 0
    assert not rdb_client.session.registry.has()


def test_validation_error_releases_owned_session(client):
    rdb_client, engine = client
    with pytest.raises(ValidationError):
        rdb_client.list(Record, obj_out=InvalidResource)
    assert engine.pool.checkedout() == 0
    assert not rdb_client.session.registry.has()


def test_get_keeps_caller_session_and_pending_transaction(client):
    rdb_client, engine = client
    with Session(engine) as db:
        pending = Record(name="pending")
        db.add(pending)
        assert rdb_client.get(Record, 1, db=db).name == "zero"
        assert inspect(pending).persistent
        assert db.in_transaction()
        db.commit()
    with Session(engine) as db:
        assert db.query(Record).filter_by(name="pending").count() == 1


def test_owned_call_does_not_reuse_scoped_caller_session(client):
    rdb_client, _ = client
    db = rdb_client.session()
    pending = Record(name="pending")
    db.add(pending)
    assert rdb_client.total(Record) == 3
    assert pending in db.new
    db.commit()
    assert rdb_client.total(Record) == 4


def test_create_honors_integer_autoincrement_and_returns_defaults(client):
    rdb_client, engine = client
    created = rdb_client.create(Record, RecordCreate(name="created"))
    assert isinstance(created.id, int)
    assert created.name == "created"
    assert isinstance(created.created_at, datetime)
    assert inspect(created).detached
    assert engine.pool.checkedout() == 0
    assert rdb_client.get(Record, created.id).name == "created"


def test_string_primary_key_fallback_and_model_default(client):
    rdb_client, _ = client
    class NameCreate(BaseModel):
        name: str

    created = rdb_client.create(PlainRecord, NameCreate(name="string"), primary_key_column_name="key")
    assert uuid.UUID(created.key).hex == created.key
    assert rdb_client.get(PlainRecord, created.key, primary_key_column_name="key").name == "string"
    assert rdb_client.total(PlainRecord) == 1
    assert rdb_client.create(DefaultKeyRecord, EmptyCreate()).id == "database-default"


def test_native_uuid_and_server_defaults_are_populated(client):
    rdb_client, _ = client
    created = rdb_client.bulk_save(UUIDRecord, [EmptyCreate(), EmptyCreate()])
    assert all(isinstance(row.id, uuid.UUID) for row in created)
    assert len({row.id for row in created}) == 2
    assert all(row.name == "server-default" for row in created)


def test_custom_soft_delete_column_and_disabling_filter(client):
    rdb_client, engine = client
    with Session(engine) as db:
        db.add_all([CustomDeleteRecord(id=1), CustomDeleteRecord(id=2, deleted=True)])
        db.commit()
    options = {"deleted_status_column_name": "deleted"}
    assert rdb_client.total(CustomDeleteRecord, **options) == 1
    assert rdb_client.get(CustomDeleteRecord, 2, **options) is None
    assert rdb_client.get_paging(CustomDeleteRecord, **options)[0] == 1
    assert rdb_client.total(CustomDeleteRecord, deleted_status_column_name=None) == 2
    rdb_client.delete(CustomDeleteRecord, 1, **options)
    assert rdb_client.total(CustomDeleteRecord, **options) == 0


@pytest.mark.parametrize("method", ["list", "total", "get_paging"])
def test_unknown_filter_columns_fail_explicitly(client, method):
    rdb_client, engine = client
    with pytest.raises(ValueError, match="Unknown column"):
        getattr(rdb_client, method)(Record, conditions={"scroe": 0})
    assert engine.pool.checkedout() == 0


def test_output_schema_supports_attribute_aliases(client):
    class AliasedResource(BaseModel):
        display_name: str = Field(validation_alias="name")

    rdb_client, _ = client
    assert rdb_client.get(Record, 1, obj_out=AliasedResource).display_name == "zero"


def test_bulk_save_returns_persisted_defaults(client):
    rdb_client, engine = client
    created = rdb_client.bulk_save(
        Record, [RecordCreate(name="bulk-a"), RecordCreate(name="bulk-b")], obj_out=RecordResource,
    )
    assert len({row.id for row in created}) == 2
    assert all(isinstance(row.created_at, datetime) for row in created)
    assert engine.pool.checkedout() == 0
    assert rdb_client.total(Record) == 5


def test_bulk_failure_is_atomic(client):
    rdb_client, engine = client
    with pytest.raises(IntegrityError):
        rdb_client.bulk_save(Record, [RecordCreate(name="bulk-a", id=10), RecordCreate(name="zero", id=11)])
    with Session(engine) as db:
        assert db.query(Record).filter_by(name="bulk-a").count() == 0
    assert engine.pool.checkedout() == 0


@pytest.mark.parametrize("identify", ["argument", "input", "object"])
def test_update_accepts_each_primary_key_source(client, identify):
    rdb_client, _ = client
    data: dict[str, Any] = {"name": "updated"}
    options = {}
    if identify == "argument":
        options["primary_key_id"] = 1
    elif identify == "input":
        data["id"] = 1
    else:
        options["db_obj"] = rdb_client.get(Record, 1)
    updated = rdb_client.update(Record, data, obj_out=RecordResource, **options)
    assert updated.id == 1
    assert updated.name == "updated"
    assert updated.score == 0
    assert isinstance(updated.created_at, datetime)
    assert rdb_client.get(Record, 1).name == "updated"


def test_partial_update_does_not_overwrite_unset_defaults(client):
    rdb_client, _ = client
    updated = rdb_client.update(Record, RecordPatch(score=2, note=None), primary_key_id=1)
    assert updated.name == "zero"
    assert updated.score == 2
    assert updated.enabled is False
    assert updated.note is None


def test_update_accepts_zero_id_and_returns_none_for_missing_record(client):
    rdb_client, engine = client
    with Session(engine) as db:
        db.add(Record(id=0, name="id-zero"))
        db.commit()
    assert rdb_client.update(Record, {"score": 3}, primary_key_id=0).score == 3
    assert rdb_client.update(Record, {"score": 3}, primary_key_id=999, obj_out=RecordResource) is None


def test_update_rejects_conflicting_ids_before_mutation(client):
    rdb_client, _ = client
    with pytest.raises(ValueError):
        rdb_client.update(Record, {"id": 2, "name": "bad"}, primary_key_id=1)
    assert rdb_client.get(Record, 1).name == "zero"
    assert rdb_client.get(Record, 2).name == "one"


@pytest.mark.parametrize("operation", ["create", "bulk_save", "update", "delete", "physical_delete", "sql"])
def test_auto_commit_false_requires_caller_session(client, operation):
    rdb_client, engine = client
    with pytest.raises(ValueError, match="auto_commit=False"):
        if operation == "create":
            rdb_client.create(Record, RecordCreate(name="created"), auto_commit=False)
        elif operation == "bulk_save":
            rdb_client.bulk_save(Record, [RecordCreate(name="created")], auto_commit=False)
        elif operation == "update":
            rdb_client.update(Record, {"id": 1, "score": 2}, primary_key_id=1, auto_commit=False)
        elif operation == "delete":
            rdb_client.delete(Record, 1, auto_commit=False)
        elif operation == "physical_delete":
            rdb_client.physical_delete(Record, 1, auto_commit=False)
        else:
            rdb_client.execute_sql("UPDATE records SET score=2 WHERE id=1", auto_commit=False)
    assert engine.pool.checkedout() == 0


@pytest.mark.parametrize("operation", ["create", "bulk_save", "update", "delete", "physical_delete", "sql"])
def test_manual_transaction_keeps_changes_until_caller_commit(client, operation):
    rdb_client, engine = client
    with Session(engine) as db:
        if operation == "create":
            rdb_client.create(Record, RecordCreate(name="created", id=10), db=db, auto_commit=False)
        elif operation == "bulk_save":
            rdb_client.bulk_save(Record, [RecordCreate(name="created", id=10)], db=db, auto_commit=False)
        elif operation == "update":
            rdb_client.update(Record, {"id": 1, "score": 2}, db=db, primary_key_id=1, auto_commit=False)
        elif operation == "delete":
            rdb_client.delete(Record, 1, db=db, auto_commit=False)
        elif operation == "physical_delete":
            rdb_client.physical_delete(Record, 1, db=db, auto_commit=False)
        else:
            rdb_client.execute_sql("UPDATE records SET score=2 WHERE id=1", db=db, auto_commit=False)
        assert db.in_transaction()
        if operation in {"create", "bulk_save"}:
            assert db.query(Record).filter_by(name="created").count() == 1
        elif operation == "delete":
            row = db.get(Record, 1)
            assert row is not None
            assert row.is_deleted is True
        elif operation == "physical_delete":
            assert db.get(Record, 1) is None
        else:
            db.expire_all()
            row = db.get(Record, 1)
            assert row is not None
            assert row.score == 2
        with Session(engine) as observer:
            assert observer.query(Record).filter_by(name="created").count() == 0
            row = observer.get(Record, 1)
            assert row is not None
            assert row.is_deleted is False
            assert row.score == 0
        db.commit()
    with Session(engine) as observer:
        if operation in {"create", "bulk_save"}:
            assert observer.query(Record).filter_by(name="created").count() == 1
        elif operation == "delete":
            row = observer.get(Record, 1)
            assert row is not None
            assert row.is_deleted is True
        elif operation == "physical_delete":
            assert observer.get(Record, 1) is None
        else:
            row = observer.get(Record, 1)
            assert row is not None
            assert row.score == 2


def test_owned_write_validates_output_before_commit(client):
    rdb_client, engine = client
    with pytest.raises(ValidationError):
        rdb_client.create(Record, RecordCreate(name="invalid-output", id=10), obj_out=InvalidResource)
    with Session(engine) as db:
        assert db.query(Record).filter_by(name="invalid-output").count() == 0
    assert engine.pool.checkedout() == 0


def test_parameterized_sql_buffers_rows_before_releasing_connection(client):
    rdb_client, engine = client
    value = "quote' OR 1=1 --"
    result = rdb_client.execute_sql("SELECT :value AS value", params={"value": value})
    assert engine.pool.checkedout() == 0
    assert result.mappings().all() == [{"value": value}]
    result = rdb_client.execute_sql("UPDATE records SET score=:score WHERE id=:id", params={"id": 1, "score": 5})
    assert result.rowcount == 1
    assert rdb_client.get(Record, 1).score == 5


def test_sql_error_releases_owned_connection(client):
    rdb_client, engine = client
    with pytest.raises(SQLAlchemyError):
        rdb_client.execute_sql("SELECT * FROM missing_table")
    assert engine.pool.checkedout() == 0
    assert rdb_client.get(Record, 1).name == "zero"


def test_manual_transaction_error_is_left_for_caller_to_rollback(client):
    rdb_client, engine = client
    with Session(engine) as db:
        created = rdb_client.create(Record, RecordCreate(name="pending"), db=db, auto_commit=False)
        with pytest.raises(ValidationError):
            rdb_client.update(Record, {"score": 8}, primary_key_id=1, db=db,
                              auto_commit=False, obj_out=InvalidResource)
        assert inspect(created).persistent
        row = db.get(Record, 1)
        assert row is not None
        assert row.score == 8
        db.rollback()
    assert rdb_client.total(Record) == 3
    assert rdb_client.get(Record, 1).score == 0


def test_caller_session_remains_open_after_managed_commit_and_error(client):
    rdb_client, engine = client
    factory = sessionmaker(bind=engine)
    with factory() as db:
        created = rdb_client.create(Record, RecordCreate(name="caller"), db=db)
        assert inspect(created).persistent
        assert created.name == "caller"
        with pytest.raises(IntegrityError):
            rdb_client.create(Record, RecordCreate(name="zero"), db=db)
        assert db.is_active
        assert rdb_client.get(Record, 1, db=db).name == "zero"


def test_explicit_sql_session_keeps_live_result_and_transaction(client):
    rdb_client, engine = client
    with Session(engine) as db:
        result = rdb_client.execute_sql("SELECT name FROM records WHERE id=:id", db=db,
                                        auto_commit=False, params={"id": 1})
        assert db.in_transaction()
        assert result.scalar_one() == "zero"
        db.rollback()


def test_transaction_context_commits_or_rolls_back_as_a_unit(client):
    rdb_client, engine = client
    with rdb_client.transaction() as db:
        rdb_client.create(Record, RecordCreate(name="tx-created"), db=db, auto_commit=False)
        rdb_client.delete(Record, 1, db=db, auto_commit=False)
    assert rdb_client.get(Record, 1) is None
    assert rdb_client.total(Record) == 3
    with pytest.raises(RuntimeError), rdb_client.transaction() as db:
        rdb_client.create(Record, RecordCreate(name="tx-failed"), db=db, auto_commit=False)
        rdb_client.delete(Record, 2, db=db, auto_commit=False)
        raise RuntimeError("abort")
    assert rdb_client.get(Record, 2).name == "one"
    with Session(engine) as db:
        assert db.query(Record).filter_by(name="tx-failed").count() == 0
    assert engine.pool.checkedout() == 0


@pytest.mark.parametrize("url, poolclass", [
    ("sqlite:///:memory:", None),
    ("sqlite:///:memory:", StaticPool),
    ("sqlite:///:memory:", NullPool),
])
def test_sqlite_url_accepts_dialect_pool_options(url, poolclass):
    options = {"poolclass": poolclass} if poolclass else {}
    client = RDBClient(url=url, **options)
    try:
        assert client.execute_sql("SELECT 1").scalar_one() == 1
    finally:
        client.session.remove()
        client.engine.dispose()


def test_sqlite_connection_components(tmp_path):
    client = RDBClient(database=str(tmp_path / "components.db"), db_type="sqlite")
    try:
        assert client.execute_sql("SELECT 1").scalar_one() == 1
    finally:
        client.engine.dispose()


def test_connection_components_preserve_special_characters():
    client = RDBClient("user@name", "p@ss:/?#%", "localhost", 3306, "database")
    try:
        assert client.engine.url.username == "user@name"
        assert client.engine.url.password == "p@ss:/?#%"
        assert client.engine.url.host == "localhost"
    finally:
        client.engine.dispose()
