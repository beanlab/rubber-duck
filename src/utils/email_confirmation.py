import boto3
import uuid
import os

from ..utils.logger import duck_logger


class EmailConfirmation:
    def __init__(self, sender_email):
        self._sender_email = sender_email
        self.token_store = {}
        self._setup()

    def _setup(self):
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION")

        if not aws_access_key_id or not aws_secret_access_key or not aws_region:
            raise EnvironmentError("AWS credentials or region not set in environment")

        self._ses_client = boto3.client(
            "ses",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region,
        )

    def generate_token(self, email):
        code = str(uuid.uuid4().int)[:6]
        self.token_store[email] = code
        return code

    def _send_email(self, email, subject, body) -> bool:
        try:
            self._ses_client.send_email(
                Source=self._sender_email,
                Destination={"ToAddresses": [email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Html": {"Data": body}},
                },
            )
            duck_logger.debug(f"Email sent to {email}")
            return True
        except Exception as e:
            duck_logger.exception("Error sending email")
            return False

    def prepare_email(self, email, token) -> str | None:
        subject = "Registration confirmation"
        body = f"""
        <html>
        <body>
            <p>Hello,</p>
            <p>Here is your secret code:</p>
            <p style="text-align: center; font-size: 24px; font-weight: bold;">{token}</p>
            <p>Use this token on Discord to verify your email.</p>
        </body>
        </html>
        """
        if self._send_email(email, subject, body):
            return token
        else:
            duck_logger.warning(f"Email not sent to {email}")
            return None
