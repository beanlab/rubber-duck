from typing import Union

from quest import BlobStorage, StepSerializer, WorkflowManager, PersistentHistory, NoopSerializer, History, WorkflowFactory
from sqlalchemy import Column, Integer, String, JSON
from sqlalchemy.orm import declarative_base

from connection import DatabaseConnection

Base = declarative_base()


Blob = Union[dict, list, str, int, bool, float]

class RecordModel(Base):
    __tablename__ = 'records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)  # TODO good name for this?
    key = Column(String)
    blob = Column(JSON)

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self.name}>'

class SqlBlobStorage(BlobStorage):
    def __init__(self, name, session):
        self._name = name
        self._session = session

    def _get_session(self):
        return self._session

    def write_blob(self, key: str, blob: Blob):
        session = self._get_session()
        record_to_update = session.query(RecordModel).filter(RecordModel.name == self._name,
                                                             RecordModel.key == key).one_or_none()
        if record_to_update:
            record_to_update.blob = blob
        else:
            new_record = RecordModel(name=self._name, key=key, blob=blob)
            session.add(new_record)
        session.commit()

    # noinspection PyTypeChecker
    def read_blob(self, key: str) -> Blob | None:
        records = self._get_session().query(RecordModel).filter(RecordModel.name == self._name).all()
        for record in records:
            if record.key == key:
                return record.blob

    def has_blob(self, key: str) -> bool:
        records = self._get_session().query(RecordModel).filter(RecordModel.name == self._name).all()
        for record in records:
            if record.key == key:
                return True
        return False

    def delete_blob(self, key: str):
        records = self._get_session().query(RecordModel).filter(RecordModel.name == self._name).all()
        for record in records:
            if record.key == key:
                self._get_session().delete(record)
                self._get_session().commit()


def create_sql_manager(
        namespace: str,
        factory: WorkflowFactory,
        serializer: StepSerializer = NoopSerializer()
) -> WorkflowManager:
    database = DatabaseConnection(Base)

    storage = SqlBlobStorage(namespace, database.get_session())

    def create_history(wid: str) -> History:
        return PersistentHistory(wid, SqlBlobStorage(wid, database.get_session()))

    return WorkflowManager(namespace, storage, create_history, factory, serializer= serializer)
