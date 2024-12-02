import boto3
import uuid
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(dotenv_path=r"C:\Users\18019\OneDrive\Desktop\cs301R\rubber-duck\secrets.env")

# AWS SES setup
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = os.getenv("AWS_REGION")

if not aws_access_key_id or not aws_secret_access_key or not aws_region:
    raise EnvironmentError("AWS credentials or region not set in .env")

ses_client = boto3.client(
    "ses",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region,
)

# In-memory token store (use persistent storage in production)
token_store = {}

def generate_token(email):
    token = str(uuid.uuid4())  # Generate a unique token
    expiration_time = int(time.time()) + 3600  # 1-hour expiration
    token_store[email] = {"token": token, "expires_at": expiration_time}
    return {"email": email, "token": token, "expires_at": expiration_time}

def retrieve_token(email):
    return token_store.get(email)

# Sender and recipient email
SENDER = "wjw37@byu.edu"  # Must be verified in AWS SES
SUBJECT = "Confirm Your Email Address"
BASE_URL = "https://wjw37byu.com"  # Base URL for your service

def send_email_with_token(email, token):
    confirmation_link = f"{BASE_URL}/confirm-email?token={token}&email={email}"
    body = f"""
    <html>
    <body>
        <p>Hello,</p>
        <p>Please confirm your email address by clicking the link below:</p>
        <a href="{confirmation_link}">Confirm Email</a>
    </body>
    </html>
    """
    try:
        response = ses_client.send_email(
            Source=SENDER,
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": SUBJECT},
                "Body": {"Html": {"Data": body}},
            },
        )
        print("Email sent! Message ID:", response["MessageId"])
    except Exception as e:
        print("Error sending email:", e)

# Example usage
test_email = "wjw37@byu.edu"
token_data = generate_token(test_email)
send_email_with_token(test_email, token_data["token"])
