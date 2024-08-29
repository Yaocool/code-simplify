import uuid
from typing import Any, Dict, Generic, List, Type, TypeVar, Tuple

from pydantic import BaseModel
from sqlalchemy import create_engine, Result
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, Session, scoped_session
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

RDBBase = declarative_base()
ModelType = TypeVar("ModelType", bound=RDBBase)
SchemaMutType = TypeVar("SchemaMutType", bound=BaseModel)
SchemaResourceType = TypeVar("SchemaResourceType", bound=BaseModel)


class RDBClient(Generic[ModelType, SchemaMutType, SchemaResourceType]):
    def __init__(
            self,
            user: str,
            password: str,
            host: str,
            port: int,
            database: str,
            db_type: str = 'mysql+pymysql',
            max_overflow: int = 0,
            pool_size: int = 50,
            pool_timeout: int = 50,
            pool_recycle: int = 5,
            echo: bool = False,
            **kwargs
    ):
        engine = create_engine(
            f"{db_type}://{user}:{password}@{host}:"
            f"{port}/{database}",
            max_overflow=max_overflow,
            pool_size=pool_size,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            echo=echo,
            **kwargs
        )
        self.session = scoped_session(sessionmaker(bind=engine))

    def get(
            self,
            model: Type[ModelType],
            primary_key_id: int | str,
            db: Session = None,
            primary_key_column_name: str = 'id',
            obj_out: Type[SchemaResourceType] = None,
            deleted_status_column_name: str = 'is_deleted',
            range_all=False
    ) -> SchemaResourceType | ModelType:
        """
         Get record by id.
        :param model: Model bound with `Base`
        :param primary_key_id: primary key id
        :param db: session
        :param primary_key_column_name: primary key column name
        :param obj_out: obj output type
        :param deleted_status_column_name: deleted status column name
        :param range_all: query range
        :return: SchemaResourceType | ModelType
        """
        db = db or self.session()
        filter_conditions = [
            getattr(model, primary_key_column_name) == primary_key_id
        ]
        if deleted_status_column_name:
            filter_conditions.append(
                getattr(model, deleted_status_column_name) == range_all
            )
        data = db.query(model).filter(*filter_conditions).first()
        if obj_out:
            return obj_out(**data.dict())
        db.close()
        return data

    def list(
            self,
            model: Type[ModelType],
            db: Session = None,
            deleted_status_column_name: str = 'is_deleted',
            range_all=True,
            obj_out: Type[SchemaResourceType] = None,
            conditions: SchemaMutType = None
    ) -> List[SchemaResourceType] | List[ModelType]:
        """
         List all records from db which is not softy deleted.
        :param model: Model bound with `Base`
        :param db: db session
        :param deleted_status_column_name:
        :param range_all:
        :param obj_out: object output type, default is model type
        :param conditions: where clause
        :return:
        """
        filter_conditions = []
        db = db or self.session()
        if conditions:
            for k, v in conditions.__dict__.items():
                if hasattr(model, k) and v:
                    filter_conditions.append(getattr(model, k) == v)
        if deleted_status_column_name:
            filter_conditions.append(
                getattr(model, deleted_status_column_name) == range_all
            )
        data = db.query(model).filter(*filter_conditions).all()
        if obj_out:
            return [obj_out(**o.__dict__) for o in data]
        db.close()
        return data

    def get_paging(
            self,
            model: Type[ModelType],
            db: Session = None,
            page: int = 1,
            page_size: int = 20,
            order_by_type: str = 'desc',  # or 'asc'
            order_by_column_name: str = 'id',
            conditions: SchemaMutType = None,
            obj_out: Type[SchemaResourceType] = None,
    ) -> Tuple[int, List[ModelType | SchemaResourceType]]:
        """
         Get paging records.
        :param model: model bound with `Base`
        :param db: db session
        :param page: page number
        :param page_size: page size
        :param order_by_type: order by type, default is desc
        :param order_by_column_name: order by column name
        :param conditions: where clause
        :param obj_out: object output type, default is model type
        :return: total, paging data
        """
        if order_by_type == 'desc':
            order_by_column_name = '-' + order_by_column_name
        elif order_by_type == 'asc':
            pass
        else:
            raise ValueError('order_by_type must be asc or desc')
        db = db or self.session()
        query = db.query(model)
        filter_conditions = []
        if conditions:
            for k, v in conditions.__dict__.items():
                if hasattr(model, k) and v:
                    filter_conditions.append(getattr(model, k) == v)
        total = query.count()
        if total == 0:
            return total, []
        skip = page_size * (page - 1)
        data = query.order_by(order_by_column_name).offset(skip).limit(page_size).filter(
            *filter_conditions
        ).all()
        if obj_out:
            return total, [obj_out(**o.__dict__) for o in data]
        db.close()
        return total, data

    def total(
            self,
            model: Type[ModelType],
            db: Session = None,
            conditions: SchemaMutType = None,
    ) -> int:
        """
         Get total count.
        :param model: Model bound with `Base`
        :param db: db session
        :param conditions: where clause
        :return:
        """
        db = db or self.session()
        filter_conditions = []
        if conditions:
            for k, v in conditions.__dict__.items():
                if hasattr(model, k) and v:
                    filter_conditions.append(getattr(model, k) == v)
        total_count = db.query(model).filter(*filter_conditions).count()
        db.close()
        return total_count

    def bulk_save(
            self,
            model: Type[ModelType],
            obj_in: List[SchemaMutType],
            db: Session = None,
            obj_out: Type[SchemaResourceType] = None,
            primary_key_column_name='id',
            auto_commit=True
    ) -> List[SchemaResourceType] | List[ModelType]:
        """
         Bulk save records to database.
        :param model: Model bound with `Base`
        :param db: db session
        :param obj_in: input object which need to be saved and isinstance of `SchemaMutType`
        :param obj_out: output object which isinstance of `SchemaResourceType`,
               all data contain id(default is uuid)
        :param primary_key_column_name: primary key column name
        :param auto_commit:
        :return: List[SchemaResourceType] | List[ModelType]
        """
        db = db or self.session()
        db_objs = []
        for obj in obj_in:
            db_obj = model(**obj.dict())
            if not hasattr(obj, primary_key_column_name) or getattr(obj, primary_key_column_name) is None:
                setattr(db_obj, primary_key_column_name, uuid.uuid4().hex)
            db_objs.append(db_obj)
        try:
            db.bulk_save_objects(db_objs)
            if auto_commit:
                db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            db.close()
            raise e
        if obj_out:
            return [obj_out(**o.__dict__) for o in db_objs]
        db.close()
        return db_objs

    def create(
            self,
            model: Type[ModelType],
            obj_in: SchemaMutType,
            db: Session = None,
            obj_out: Type[SchemaResourceType] = None,
            primary_key_column_name='id',
            auto_commit=True
    ) -> SchemaResourceType | ModelType:
        """
         Insert one record to database.
        :param model: Model bound with `Base`
        :param db: db session
        :param obj_in: input object which need to be saved and isinstance of `SchemaMutType`
        :param obj_out: output object which isinstance of `SchemaResourceType` and contains id(default is uuid)
        :param primary_key_column_name: primary key column name
        :param auto_commit:
        :return: SchemaResourceType | ModelType
        """
        db = db or self.session()
        db_obj = model(**obj_in.dict())
        if not hasattr(obj_in, primary_key_column_name) or getattr(obj_in, primary_key_column_name) is None:
            setattr(db_obj, primary_key_column_name, uuid.uuid4().hex)
        try:
            db.add(db_obj)
            if auto_commit:
                db.commit()
                db.refresh(db_obj)
            else:
                db.flush([db_obj])
        except SQLAlchemyError as e:
            db.rollback()
            db.close()
            raise e
        if obj_out:
            return obj_out(**db_obj.__dict__)
        db.close()
        return db_obj

    def update(
            self,
            model: Type[ModelType],
            obj_in: SchemaMutType | Dict[str, Any],
            db: Session = None,
            primary_key_id: int | str = None,
            primary_key_column_name='id',
            db_obj: ModelType = None,
            obj_out: Type[SchemaResourceType] = None,
            auto_commit=True
    ) -> SchemaResourceType | ModelType:
        """
         Update one record to database.
        :param model: Model bound with `Base`
        :param primary_key_id: primary key id
        :param db: db session
        :param primary_key_column_name: primary key column name
        :param db_obj: db object
        :param obj_in: input object which need to be saved and isinstance of `SchemaMutType`
        :param obj_out: output object which isinstance of `SchemaResourceType` and contains updated values
        :param auto_commit:
        :return: SchemaResourceType | ModelType
        """
        db = db or self.session()
        db_obj = db_obj or model()
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.dict()
        for field in update_data.keys():
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])
        if not all([primary_key_id, update_data.get(primary_key_column_name)]):
            raise ValueError('Neither obj_in nor primary_key_id found an id.')
        _id = update_data.get(primary_key_column_name)
        if primary_key_id:
            _id = primary_key_id
        setattr(db_obj, primary_key_column_name, _id)
        try:
            db.query(model).filter(
                getattr(model, primary_key_column_name) == _id
            ).update(update_data)
            if auto_commit:
                db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            db.close()
            raise e
        if obj_out:
            return obj_out(**db_obj.__dict__)
        db.close()
        return db_obj

    def delete(
            self,
            model: Type[ModelType],
            primary_key_ids: int | str | List[int] | List[str],
            db: Session = None,
            primary_key_column_name: str = 'id',
            deleted_status_column_name: str = 'is_deleted',
            auto_commit=True
    ):
        """
         Soft delete, just update record deleted flag. Supports batch deletion and single deletion.
         Default deleted status column name is 'is_deleted'.
        :param model: model bound with `Base`
        :param primary_key_ids: primary key id
        :param db: db session
        :param primary_key_column_name: primary key column name
        :param deleted_status_column_name: deleted status column name
        :param auto_commit:
        :return: None, if raised exception, will roll back and close db session, which means this operation is failed
        """
        db = db or self.session()
        try:
            if isinstance(primary_key_ids, list):
                filter_condition = getattr(
                    model, primary_key_column_name
                ).in_(primary_key_ids)
            else:
                filter_condition = getattr(
                    model, primary_key_column_name
                ) == primary_key_ids
            db.query(model).filter(filter_condition).update(
                {deleted_status_column_name: True})
            if auto_commit:
                db.commit()
            db.close()
        except SQLAlchemyError as e:
            db.rollback()
            db.close()
            raise e

    def physical_delete(
            self,
            model: Type[ModelType],
            primary_key_id: int | str,
            db: Session = None,
            primary_key_column_name: str = 'id',
            auto_commit=True
    ):
        """
         Physical delete, delete the record directly from the database.
        :param model: model bound with `Base`
        :param primary_key_id: primary key id
        :param db: db session
        :param primary_key_column_name: primary key column name
        :param auto_commit:
        :return: None, if raised exception, will roll back and close db session, which means this operation is failed
        """
        db = db or self.session()
        try:
            obj = db.query(model).filter(
                getattr(model, primary_key_column_name) == primary_key_id
            ).first()
            if obj:
                db.delete(obj)
            if auto_commit:
                db.commit()
            db.close()
        except SQLAlchemyError as e:
            db.rollback()
            db.close()
            raise e

    def execute_sql(
            self,
            sql: str,
            db: Session = None,
            auto_commit=True,
    ) -> Result[Any]:
        """
         Execute sql statement.
        :param sql: sql
        :param db: db session
        :param auto_commit:
        :return: Result[Any] from SQLAlchemy Result
        """
        db = db or self.session()
        try:
            result = db.execute(text(sql))
            if auto_commit:
                db.commit()
            db.close()
            return result
        except SQLAlchemyError as e:
            db.rollback()
            db.close()
            raise e
