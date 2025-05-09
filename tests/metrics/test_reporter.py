import os
from pathlib import Path
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import yaml

from src.storage.sql_connection import create_sql_session
from src.storage.sql_metrics import SQLMetricsHandler, MessagesModel, UsageModel, FeedbackModel
from src.metrics.reporter import Reporter

@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary database path for testing"""
    return tmp_path / "test_metrics.db"

@pytest.fixture
def test_config_path(tmp_path):
    """Create a temporary config file for testing"""
    config = {
        "sql": {
            "url": f"sqlite:///{tmp_path}/test_metrics.db"
        },
        "reporting": {
            "123456789": "Test Class 1",
            "987654321": "Test Class 2"
        }
    }
    config_path = tmp_path / "test_config.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    return config_path

@pytest.fixture
def test_db(test_db_path):
    """Create a test database with sample data"""
    sql_session = create_sql_session({"url": f"sqlite:///{test_db_path}"})
    
    # Create tables
    SQLMetricsHandler(sql_session)
    
    # Add test data
    now = datetime.now(ZoneInfo('US/Mountain'))
    
    # Add messages
    for i in range(10):
        message = MessagesModel(
            timestamp=(now - timedelta(days=i)).isoformat(),
            guild_id=123456789 if i % 2 == 0 else 987654321,
            thread_id=1000 + i,
            user_id=2000 + i,
            role="student",
            message=f"Test message {i}"
        )
        sql_session.add(message)
    
    # Add usage data
    for i in range(10):
        usage = UsageModel(
            timestamp=(now - timedelta(days=i)).isoformat(),
            guild_id=123456789 if i % 2 == 0 else 987654321,
            thread_id=1000 + i,
            user_id=2000 + i,
            engine="gpt-4",
            input_tokens="100",
            output_tokens="200"
        )
        sql_session.add(usage)
    
    # Add feedback data
    for i in range(10):
        feedback = FeedbackModel(
            timestamp=(now - timedelta(days=i)).isoformat(),
            workflow_type="basic",
            guild_id=123456789 if i % 2 == 0 else 987654321,
            thread_id=1000 + i,
            user_id=2000 + i,
            reviewer_role_id=3000 + i,
            feedback_score=i % 5 + 1
        )
        sql_session.add(feedback)
    
    sql_session.commit()
    sql_session.close()
    
    return test_db_path

def test_reporter_initialization(test_db_path, test_config_path):
    """Test that the reporter can be initialized with test data"""
    # Load config
    with open(test_config_path) as f:
        config = yaml.safe_load(f)
    
    # Create SQL session and metrics handler
    sql_session = create_sql_session(config['sql'])
    metrics_handler = SQLMetricsHandler(sql_session)
    
    # Create reporter
    reporter = Reporter(metrics_handler, config['reporting'], show_fig=False)
    
    # Test a simple report
    report_name, report_data = reporter.get_report('!report f1')
    assert report_name is not None
    assert report_data is not None

def test_reporter_help_menu(test_db_path, test_config_path):
    """Test that the help menu works"""
    # Load config
    with open(test_config_path) as f:
        config = yaml.safe_load(f)
    
    # Create SQL session and metrics handler
    sql_session = create_sql_session(config['sql'])
    metrics_handler = SQLMetricsHandler(sql_session)
    
    # Create reporter
    reporter = Reporter(metrics_handler, config['reporting'], show_fig=False)
    
    # Test help menu
    help_text, _ = reporter.get_report('!report help')
    assert help_text is not None
    assert isinstance(help_text, str)
    assert "Type '!report'" in help_text

def test_reporter_feedback_trends(test_db_path, test_config_path):
    """Test that feedback trend reports work"""
    # Load config
    with open(test_config_path) as f:
        config = yaml.safe_load(f)
    
    # Create SQL session and metrics handler
    sql_session = create_sql_session(config['sql'])
    metrics_handler = SQLMetricsHandler(sql_session)
    
    # Create reporter
    reporter = Reporter(metrics_handler, config['reporting'], show_fig=False)
    
    # Test feedback trend reports
    for report_type in ['ftrend percent', 'ftrend average']:
        report_name, report_data = reporter.get_report(f'!report {report_type}')
        assert report_name is not None
        assert report_data is not None 