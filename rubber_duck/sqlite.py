from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_sqlite_session(db_url: str) -> Session:
    engine = create_engine(db_url)
    return sessionmaker(bind=engine)()


def create_sql_session(db_type: str, username: str, password: str, host: str, port: str, database: str) -> Session:
    db_url = f"{db_type}://{username}:{password}@{host}:{port}/{database}"
    engine = create_engine(db_url)
    return sessionmaker(bind=engine)()

