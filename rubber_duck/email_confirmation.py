import boto3
import uuid
import os
from dotenv import load_dotenv

class EmailConfirmation:
    def __init__(self):
        self.token_store = {}
        self._setup()

    def _setup(self):
        # Load environment variables from .env
        load_dotenv(dotenv_path=r"C:\Users\18019\OneDrive\Desktop\cs301R\rubber-duck\secrets.env")

        # AWS SES setup
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION")

        if not aws_access_key_id or not aws_secret_access_key or not aws_region:
            raise EnvironmentError("AWS credentials or region not set in .env")

        self.ses_client = boto3.client(
            "ses",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region,
        )

    def confirm_token(self, email, user_response_token) -> bool:

        return user_response_token in self.token_store.values()

    def generate_token(self, email):
        # Generate a UUID
        unique_id = uuid.uuid4()
        # Convert the UUID to a string and take the first 6 digits
        code = str(unique_id.int)[:6]
        self.token_store[email] = code
        return code

    def _retrieve_token(self, email):
        return self.token_store.get(email)

    def send_email_with_token(self, email, sender):
        token = self.generate_token(email)
        # Sender and recipient email
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
        try:
            response = self.ses_client.send_email(
                Source=sender,
                Destination={"ToAddresses": [email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Html": {"Data": body}},
                },
            )
            print("Email sent! Message ID:", response["MessageId"])
        except Exception as e:
            print("Error sending email:", e)

