# File: db_connection.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class DatabaseConnection:
    def __init__(self, base, db_url='sqlite:///rubber_duck_database.db'):
        # Initialize the database connection
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        # Create tables if they do not exist
        base.metadata.create_all(self.engine)

    def get_session(self):
        # Provide a new session
        return self.Session()