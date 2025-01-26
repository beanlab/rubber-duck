import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from quest import step

def setUpConnection():
    # Connection Object
    connection = sqlite3.connect('../state/database.db')
    # Cursor object
    cursor = connection.cursor()
    return connection, cursor
    # Needs to figure out
    # connection.close()


def get_timestamp():
    return datetime.now(ZoneInfo('US/Mountain')).isoformat()


class SQLMetricsHandler:
    def __init__(self):
        self.connection, self.cursor = setUpConnection()
        # SQL Create Table Strings
        createMessagesTable = """ 
            CREATE TABLE IF NOT EXISTS messages (
                timestamp DATETIME,
                guild_id INT,
                thread_id INT,
                user_id INT,
                role TEXT,
                message TEXT
                ); """
        createUsageTable = """ 
            CREATE TABLE IF NOT EXISTS usage (
                timestamp DATETIME,
                guild_id INT,
                thread_id INT,
                user_id INT,
                engine TEXT,
                input_tokens TEXT,
                output_tokens TEXT
                ); """
        createFeedbackTable = """ 
            CREATE TABLE IF NOT EXISTS feedback (
                timestamp DATETIME,
                guild_id INT,
                thread_id INT,
                user_id INT,
                reviewer_role_id INT,
                feedback_score INT
                ); """
        # Execute the SQL queries
        self.cursor.execute(createMessagesTable)
        self.connection.commit()
        self.cursor.execute(createUsageTable)
        self.connection.commit()
        self.cursor.execute(createFeedbackTable)
        self.connection.commit()

    @step
    async def record_message(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str):
        try:
            insertMessage = """ 
                INSERT INTO messages (timestamp, guild_id, thread_id, user_id, role, message)
                    VALUES($1, $2, $3, $4, $5, $6); """
            self.cursor.execute(insertMessage, (get_timestamp(), guild_id, thread_id, user_id, role, message))
            self.connection.commit()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    @step
    async def record_usage(self, guild_id, thread_id, user_id, engine, input_tokens, output_tokens):
        try:
            insertUsage = """ 
                INSERT INTO usage (timestamp, guild_id, thread_id, user_id, engine, input_tokens, output_tokens)
                    VALUES($1, $2, $3, $4, $5, $6, $7); """
            self.cursor.execute(insertUsage, (get_timestamp(), guild_id, thread_id, user_id, engine, input_tokens, output_tokens))
            self.connection.commit()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    @step
    async def record_feedback(self, guild_id: int, thread_id: int, user_id: int, feedback_score: int, reviewer_id: int):
        try:
            insertFeedback = """ 
                INSERT INTO feedback (timestamp, guild_id, thread_id, user_id, feedback_score, reviewer_id)
                    VALUES($1, $2, $3, $4, $5, $6); """
            self.cursor.execute(insertFeedback, (get_timestamp(), guild_id, thread_id, user_id, feedback_score, reviewer_id))
            self.connection.commit()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    def get_message(self):
        messagesTable = """ SELECT * FROM messages """
        return self.cursor.execute(messagesTable)


    def get_usage(self):
        usageTable = """ SELECT * FROM usage """
        return self.cursor.execute(usageTable)


    def get_feedback(self):
        feedbackTable = """ SELECT * FROM feedback """
        return self.cursor.execute(feedbackTable)
