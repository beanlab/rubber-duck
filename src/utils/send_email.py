import os
import re

import boto3

from ..utils.logger import duck_logger


class EmailSender:
    def __init__(self, sender_email):
        self._sender_email = sender_email
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

    def _check_email(self, netid: str) -> bool:
        if not netid:
            return False

        # Regex: netid (5–8 chars, starts with letter, lowercase letters/numbers only) + @byu.edu
        NETID_REGEX = re.compile(r"^[a-z][a-z0-9]{4,7}@byu\.edu$")

        return bool(NETID_REGEX.match(netid))

    def _send_email(self, email, subject, body) -> bool:
        try:
            if self._check_email(email):
                self._ses_client.send_email(
                    Source=self._sender_email,
                    Destination={"ToAddresses": [email]},
                    Message={
                        "Subject": {"Data": subject},
                        "Body": {"Html": {"Data": body}},
                    },
                )
                duck_logger.info(f"Email sent to {email}")
                return True
            else:
                duck_logger.info(f"Invalid email address: {email}")
                return False
        except Exception as e:
            duck_logger.info("Error sending email")
            return False

    def send_email(self, email, token) -> str | None:
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
        try:
            if self._send_email(email, subject, body):
                return token
            else:
                duck_logger.info(f"Email not sent to {email}")
                return None
        except Exception as e:
            raise
