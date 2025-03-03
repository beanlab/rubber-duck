import os
from typing import TypedDict

from distlib.util import resolve
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _create_sqlite_session(db_name: str) -> Session:
    db_url = f"sqlite:///{db_name}"
    engine = create_engine(db_url)
    return sessionmaker(bind=engine)()


def _create_sql_session(db_type: str, username: str, password: str, host: str, port: str, database: str) -> Session:
    db_url = f"{db_type}://{username}:{password}@{host}:{port}/{database}"
    engine = create_engine(db_url)
    return sessionmaker(bind=engine)()


class SqlConfig(TypedDict):
    db_type: str
    username: str
    password: str
    host: str
    port: str
    database: str


def resolve_env_vars(config):
    return {
        key: os.getenv(value[len('env:'):]) if value.startswith('env:') else value
        for key, value in config.items()
    }


def create_sql_session(config: SqlConfig) -> Session:
    config = resolve_env_vars(config)
    if config['db_type'] == 'sqlite':
        return _create_sqlite_session(config['database'])
    else:
        return _create_sql_session(**config)
