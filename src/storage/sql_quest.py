from typing import Union

from quest import BlobStorage, StepSerializer, WorkflowManager, PersistentHistory, NoopSerializer, History, \
    WorkflowFactory
from sqlalchemy import Column, Integer, String, JSON
from sqlalchemy.orm import declarative_base, Session

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
