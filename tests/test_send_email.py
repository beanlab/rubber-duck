from unittest.mock import Mock

from src.utils.send_email import EmailSender


def test_email_sender_uses_boto_default_credentials(monkeypatch):
    client = Mock()
    boto_client = Mock(return_value=client)
    monkeypatch.setattr("src.utils.send_email.boto3.client", boto_client)
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "legacy-access-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "legacy-secret-key")

    sender = EmailSender("sender@example.com")

    assert sender._ses_client is client
    boto_client.assert_called_once_with("ses", region_name="us-west-2")


def test_email_sender_supports_default_region(monkeypatch):
    boto_client = Mock()
    monkeypatch.setattr("src.utils.send_email.boto3.client", boto_client)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")

    EmailSender("sender@example.com")

    boto_client.assert_called_once_with("ses", region_name="us-west-2")
