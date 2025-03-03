import os
from typing import TypedDict

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker


def _create_sqlite_session(db_name: str) -> Session:
    db_url = f"sqlite:///{db_name}"
    engine = create_engine(db_url)
    return sessionmaker(bind=engine)()


def _create_sql_session(db_type: str, username: str, password: str, host: str, port: str, database: str) -> Session:
    server_url = f"{db_type}://{username}:{password}@{host}:{port}"
    db_url = f"{server_url}/{database}"

    try:
        # Try to create an engine with the database
        engine = create_engine(db_url)
        engine.connect()
    except OperationalError:
        # If the database does not exist, connect to the server without specifying the database
        engine = create_engine(server_url)
        conn = engine.connect()
        conn.execute(f"CREATE DATABASE {database}")
        conn.close()

        # Now connect to the newly created database
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
