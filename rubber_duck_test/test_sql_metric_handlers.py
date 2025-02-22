import pytest
from rubber_duck.sql_metrics import SQLMetricsHandler
from rubber_duck.sqlite import create_sqlite_session

class TestSQLMetrics:
    @classmethod
    def setup_class(cls):
        """Set up the in-memory SQLite session and SQL handler."""
        cls.test_values = {
            "workflow_type":"test-workflow",
            "guild_id": 1234,
            "thread_id": 5678,
            "user_id": 123456789,
            "role": "test-role",
            "message": "test-message",
            "engine": "test-engine",
            "input_tokens": "test-input-token",
            "output_tokens": "test-output-token",
            "reviewer_role_id": 987654,
            "feedback_score": 4
        }
        cls.session = create_sqlite_session('sqlite:///:memory:')
        cls.sql_handler = SQLMetricsHandler(cls.session)

    @pytest.mark.asyncio
    async def test_messages_table(self):
        """Test recording and retrieving messages."""
        await self.sql_handler.record_message(
            self.test_values["guild_id"], self.test_values["thread_id"], self.test_values["user_id"],
            self.test_values["role"], self.test_values["message"]
        )

        recorded_messages = self.sql_handler.get_message()

        assert recorded_messages is not None
        assert recorded_messages[0].guild_id == self.test_values["guild_id"]
        assert recorded_messages[0].thread_id == self.test_values["thread_id"]
        assert recorded_messages[0].user_id == self.test_values["user_id"]
        assert recorded_messages[0].role == self.test_values["role"]
        assert recorded_messages[0].message == self.test_values["message"]

    @pytest.mark.asyncio
    async def test_usage_table(self):
        """Test recording and retrieving usage data."""
        await self.sql_handler.record_usage(
            self.test_values["guild_id"], self.test_values["thread_id"], self.test_values["user_id"],
            self.test_values["engine"], self.test_values["input_tokens"], self.test_values["output_tokens"]
        )

        recorded_usages = self.sql_handler.get_usage()

        assert recorded_usages is not None
        assert recorded_usages[0].guild_id == self.test_values["guild_id"]
        assert recorded_usages[0].thread_id == self.test_values["thread_id"]
        assert recorded_usages[0].user_id == self.test_values["user_id"]
        assert recorded_usages[0].engine == self.test_values["engine"]
        assert recorded_usages[0].input_tokens == self.test_values["input_tokens"]
        assert recorded_usages[0].output_tokens == self.test_values["output_tokens"]

    @pytest.mark.asyncio
    async def test_feedback_table(self):
        """Test recording and retrieving feedback."""
        await self.sql_handler.record_feedback(
            self.test_values["workflow_type"],
            self.test_values["guild_id"],
            self.test_values["thread_id"],
            self.test_values["user_id"],
            self.test_values["reviewer_role_id"],
            self.test_values["feedback_score"]
        )

        recorded_feedback = self.sql_handler.get_feedback()

        assert recorded_feedback is not None
        assert recorded_feedback[0].guild_id == self.test_values["guild_id"]
        assert recorded_feedback[0].thread_id == self.test_values["thread_id"]
        assert recorded_feedback[0].user_id == self.test_values["user_id"]
        assert recorded_feedback[0].feedback_score == self.test_values["feedback_score"]
        assert recorded_feedback[0].reviewer_role_id == self.test_values["reviewer_role_id"]

    @classmethod
    def run_all_tests(cls):
        """Run all test methods in this class."""
        pytest.main(["-v", "--asyncio-mode=auto"])

