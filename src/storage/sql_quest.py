from typing import Union

from quest import BlobStorage, StepSerializer, WorkflowManager, PersistentHistory, NoopSerializer, History, \
    WorkflowFactory
from sqlalchemy import Column, Integer, String, JSON
from sqlalchemy.orm import declarative_base, Session

from ..utils import load_logging

QuestRecordBase = declarative_base()

Blob = Union[dict, list, str, int, bool, float]


class RecordModel(QuestRecordBase):
    __tablename__ = 'records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))  # TODO good name for this?
    key = Column(String(255))
    blob = Column(JSON)

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self.name}>'


# TODO - migrate to using Quests version
class SqlBlobStorage(BlobStorage):
    def __init__(self, name, session):
        self._name = name
        self._session = session

    def _get_session(self):
        return self._session

    def write_blob(self, key: str, blob: Blob):
        def write():
            session = self._get_session()
            record_to_update = session.query(RecordModel).filter(
                RecordModel.name == self._name,
                RecordModel.key == key,
            ).one_or_none()
            if record_to_update:
                record_to_update.blob = blob
            else:
                session.add(RecordModel(name=self._name, key=key, blob=blob))
            session.commit()

        return load_logging.timed_sync(
            "sqlite_write_blob",
            write,
            name=self._name,
            key=key,
        )

    # noinspection PyTypeChecker
    def read_blob(self, key: str) -> Blob | None:
        def read():
            records = self._get_session().query(RecordModel).filter(
                RecordModel.name == self._name,
            ).all()
            for record in records:
                if record.key == key:
                    return record.blob
            return None

        return load_logging.timed_sync(
            "sqlite_read_blob",
            read,
            name=self._name,
            key=key,
        )

    def has_blob(self, key: str) -> bool:
        def check():
            records = self._get_session().query(RecordModel).filter(
                RecordModel.name == self._name,
            ).all()
            return any(record.key == key for record in records)

        return load_logging.timed_sync(
            "sqlite_has_blob",
            check,
            name=self._name,
            key=key,
        )

    def delete_blob(self, key: str):
        def delete():
            records = self._get_session().query(RecordModel).filter(
                RecordModel.name == self._name,
            ).all()
            for record in records:
                if record.key == key:
                    self._get_session().delete(record)
                    self._get_session().commit()

        return load_logging.timed_sync(
            "sqlite_delete_blob",
            delete,
            name=self._name,
            key=key,
        )


def create_sql_manager(
        workflow_manager_sql_namespace: str,
        factory: WorkflowFactory,
        sql_session: Session,
        serializer: StepSerializer = NoopSerializer()
) -> WorkflowManager:
    QuestRecordBase.metadata.create_all(sql_session.connection())

    workflow_manager_storage = SqlBlobStorage(workflow_manager_sql_namespace, sql_session)

    def create_history(wid: str) -> History:
        history_storage = SqlBlobStorage(wid, sql_session)
        return PersistentHistory(wid, history_storage)

    return WorkflowManager(workflow_manager_sql_namespace, workflow_manager_storage, create_history, factory,
                           serializer=serializer)
