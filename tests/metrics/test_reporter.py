import pandas as pd
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from argparse import ArgumentError

from src.metrics.reporter import Reporter


class MockSQLMetricsHandler:
    def __init__(self):
        self.feedback_data = []
        self.usage_data = []
        self._create_mock_data()

    def _create_mock_data(self):
        now = datetime.now(ZoneInfo('US/Mountain'))
        
        # Create mock feedback data for the last 30 days
        for i in range(30):
            date = now - timedelta(days=i)
            # Add data for first guild
            self.feedback_data.append({
                'timestamp': date.isoformat(),
                'guild_id': 123456789,
                'thread_id': f'thread_{i}_123456789',
                'feedback_score': 4 if i % 2 == 0 else 3
            })
            # Add data for second guild
            self.feedback_data.append({
                'timestamp': date.isoformat(),
                'guild_id': 987654321,
                'thread_id': f'thread_{i}_987654321',
                'feedback_score': 4 if i % 2 == 0 else 3
            })

        # Create mock usage data
        for i in range(30):
            date = now - timedelta(days=i)
            # Add data for first guild
            self.usage_data.append({
                'timestamp': date.isoformat(),
                'guild_id': 123456789,
                'thread_id': f'thread_{i}_123456789',
                'input_tokens': 100,
                'output_tokens': 200,
                'engine': 'gpt-4'
            })
            # Add data for second guild
            self.usage_data.append({
                'timestamp': date.isoformat(),
                'guild_id': 987654321,
                'thread_id': f'thread_{i}_987654321',
                'input_tokens': 100,
                'output_tokens': 200,
                'engine': 'gpt-4'
            })

    def get_feedback(self):
        return pd.DataFrame(self.feedback_data)

    def get_usage(self):
        return pd.DataFrame(self.usage_data)

    def get_message(self):
        return pd.DataFrame([])  # Empty DataFrame for messages since we don't need them for this test


@pytest.fixture
def mock_sql_handler():
    return MockSQLMetricsHandler()


@pytest.fixture
def reporter_config():
    return {
        "123456789": "Test Guild 1",
        "987654321": "Test Guild 2"
    }


@pytest.fixture
def reporter(mock_sql_handler, reporter_config):
    return Reporter(mock_sql_handler, reporter_config, show_fig=False)


class TestReporter:
    def test_basic_feedback_trend(self, reporter):
        """Test basic feedback trend report"""
        title, image = reporter.get_report('!report -df feedback -iv feedback_score -p month')
        assert title is not None
        assert image is not None

    def test_feedback_with_average(self, reporter):
        """Test feedback report with average calculation"""
        title, image = reporter.get_report('!report -df feedback -iv feedback_score -p month -avg')
        assert title is not None
        assert image is not None

    def test_feedback_with_count(self, reporter):
        """Test feedback report with count calculation"""
        title, image = reporter.get_report('!report -df feedback -iv feedback_score -p month -c')
        assert title is not None
        assert image is not None

    def test_feedback_with_percent(self, reporter):
        """Test feedback report with percent calculation"""
        title, image = reporter.get_report('!report -df feedback -iv feedback_score -p month -per')
        assert title is not None
        assert image is not None

    def test_feedback_with_log_scale(self, reporter):
        """Test feedback report with logarithmic scale"""
        title, image = reporter.get_report('!report -df feedback -iv feedback_score -p month -ln')
        assert title is not None
        assert image is not None

    def test_feedback_with_explanatory_var(self, reporter):
        """Test feedback report with explanatory variable"""
        title, image = reporter.get_report('!report -df feedback -iv feedback_score -p month -ev guild_id')
        assert title is not None
        assert image is not None

    def test_feedback_with_two_explanatory_vars(self, reporter):
        """Test feedback report with two explanatory variables"""
        title, image = reporter.get_report('!report -df feedback -iv feedback_score -p month -ev guild_id -ev2 thread_id')
        assert title is not None
        assert image is not None

    def test_usage_cost_trend(self, reporter):
        """Test usage cost trend report"""
        title, image = reporter.get_report('!report -df usage -iv cost -p month')
        assert title is not None
        assert image is not None

    def test_usage_with_average(self, reporter):
        """Test usage report with average calculation"""
        title, image = reporter.get_report('!report -df usage -iv cost -p month -avg')
        assert title is not None
        assert image is not None

    def test_usage_with_count(self, reporter):
        """Test usage report with count calculation"""
        title, image = reporter.get_report('!report -df usage -iv thread_id -p month -c')
        assert title is not None
        assert image is not None

    def test_usage_with_percent(self, reporter):
        """Test usage report with percent calculation"""
        title, image = reporter.get_report('!report -df usage -iv cost -p month -per')
        assert title is not None
        assert image is not None

    def test_usage_with_log_scale(self, reporter):
        """Test usage report with logarithmic scale"""
        title, image = reporter.get_report('!report -df usage -iv cost -p month -ln')
        assert title is not None
        assert image is not None

    def test_usage_with_explanatory_var(self, reporter):
        """Test usage report with explanatory variable"""
        title, image = reporter.get_report('!report -df usage -iv cost -p month -ev guild_id')
        assert title is not None
        assert image is not None

    def test_usage_with_two_explanatory_vars(self, reporter):
        """Test usage report with two explanatory variables"""
        title, image = reporter.get_report('!report -df usage -iv cost -p month -ev guild_id -ev2 thread_id')
        assert title is not None
        assert image is not None

    def test_different_time_periods(self, reporter):
        """Test reports with different time periods"""
        periods = ['day', 'week', 'month', 'year']
        for period in periods:
            title, image = reporter.get_report(f'!report -df feedback -iv feedback_score -p {period}')
            assert title is not None
            assert image is not None

    def test_invalid_dataframe(self, reporter):
        """Test report with invalid dataframe"""
        with pytest.raises(ArgumentError):
            reporter.get_report('!report -df invalid -iv feedback_score -p month')

    def test_missing_required_args(self, reporter):
        """Test report with missing required arguments"""
        with pytest.raises(SystemExit):
            reporter.get_report('!report -df feedback -p month')  # Missing -iv
