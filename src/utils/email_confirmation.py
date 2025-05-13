import logging
import boto3
import uuid
import os


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

    def _retrieve_token(self, email):
        return self.token_store.get(email)

    def send_email(self, email, subject, body):
        try:
            self._ses_client.send_email(
                Source=self._sender_email,
                Destination={"ToAddresses": [email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Html": {"Data": body}},
                },
            )
            return True
        except Exception as e:
            logging.exception("Error sending email")
            return False

    def send_email_with_token(self, email):
        token = self.generate_token(email)
        subject = "Confirm Your Email Address"
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
        return self.send_email(email, subject, body)
