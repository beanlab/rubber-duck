from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_sqlite_session(db_url: str) -> Session:
    engine = create_engine(db_url)
    return sessionmaker(bind=engine)()
