import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from quest import step

def setUpConnection():
    # Connection Object
    connection = sqlite3.connect('../state/database.db')
    # Cursor object
    c = connection.cursor()
    return c
    # Needs to figure out
    # connection.close()


def get_timestamp():
    return datetime.now(ZoneInfo('US/Mountain')).isoformat()


class SQLMetricsHandler:
    def __init__(self):
        self.databaseCursor = setUpConnection()
        # SQL Create Table Strings
        createMessagesTable = """ CREATE TABLE messages(
                                  timestamp DATETIME,
                                  guild_id INT,
                                  thread_id INT,
                                  user_id INT,
                                  role TEXT,
                                  message TEXT
                                  ); """
        createUsageTable = """ CREATE TABLE usage(
                                  timestamp DATETIME,
                                  guild_id INT,
                                  thread_id INT,
                                  user_id INT,
                                  engine TEXT,
                                  input_tokens TEXT,
                                  output_tokens TEXT
                                  ); """
        createFeedbackTable = """ CREATE TABLE feedback(
                                  timestamp DATETIME,
                                  guild_id INT,
                                  thread_id INT,
                                  user_id INT,
                                  reviewer_role_id INT,
                                  feedback_score INT
                                  ); """
        # Execute the SQL queries
        self.databaseCursor.execute(createMessagesTable)
        self.databaseCursor.execute(createUsageTable)
        self.databaseCursor.execute(createFeedbackTable)


    @step
    async def record_message(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str):
        insertMessage = """ INSERT INTO messages (timestamp, guild_id, thread_id, user_id, role, message)
                            VALUES($1, $2, $3, $4, $5, $6); """
        self.databaseCursor.execute(insertMessage, (get_timestamp(), guild_id, thread_id, user_id, role, message))

    @step
    async def record_usage(self, guild_id, thread_id, user_id, engine, input_tokens, output_tokens):
        insertUsage = """ INSERT INTO usage (timestamp, guild_id, thread_id, user_id, engine, input_tokens, output_tokens)
                                    VALUES($1, $2, $3, $4, $5, $6, $7); """
        self.databaseCursor.execute(insertUsage, (get_timestamp(), guild_id, thread_id, user_id, engine, input_tokens, output_tokens))

    @step
    async def record_feedback(self, guild_id: int, thread_id: int, user_id: int, feedback_score: int, reviewer_id: int):
        insertFeedback = """ INSERT INTO feedback (timestamp, guild_id, thread_id, user_id, feedback_score, reviewer_id)
                                            VALUES($1, $2, $3, $4, $5, $6); """
        self.databaseCursor.execute(insertFeedback, (get_timestamp(), guild_id, thread_id, user_id, feedback_score, reviewer_id))

    def get_message(self):
        messagesTable = """ SELECT * FROM messages """
        return self.databaseCursor.execute(messagesTable)


    def get_usage(self):
        usageTable = """ SELECT * FROM usage """
        return self.databaseCursor.execute(usageTable)


    def get_feedback(self):
        feedbackTable = """ SELECT * FROM feedback """
        return self.databaseCursor.execute(feedbackTable)
