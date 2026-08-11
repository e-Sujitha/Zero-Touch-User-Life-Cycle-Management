import json
import random
import string
import datetime
import urllib.parse
import base64
import boto3
from botocore.exceptions import ClientError

# Initialize AWS SDK Clients
iam = boto3.client("iam")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("OnboardingAudit")
ses = boto3.client("ses")


def generate_password(length=16):
    """Generates a password meeting IAM password policy requirements."""
    characters = string.ascii_letters + string.digits + "!@#$%^&*()"
    while True:
        password = "".join(random.choice(characters) for _ in range(length))
        if (
            any(c.isupper() for c in password)
            and any(c.islower() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*()" for c in password)
        ):
            return password


def build_slack_response(text, in_channel=False):
    """Formats a JSON response structured for Slack Slash Commands."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "response_type": "in_channel" if in_channel else "ephemeral",
            "text": text
        })
    }


def lambda_handler(event, context):
    """Main entrypoint for processing /onboard slash commands from Slack."""
    # 1. Decode and parse incoming API Gateway POST payload
    raw_body = event.get("body", "") or ""
    if event.get("isBase64Encoded", False):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    parsed_body = urllib.parse.parse_qs(raw_body)
    text = parsed_body.get("text", [""])[0].strip()
    created_by = parsed_body.get("user_name", ["Slack User"])[0]

    # 2. Input validation
    parts = text.split()
    if len(parts) < 2:
        return build_slack_response(
            "⚠️ **Invalid Usage!** Please provide both username and email.\n*Example:* `/onboard raj raj@gmail.com`",
            in_channel=False
        )

    base_username = parts[0].lower()
    email = parts[1]

    # 3. Check if base username already exists in IAM
    try:
        iam.get_user(UserName=base_username)
        return build_slack_response(
            f"❌ **User Creation Aborted:** Base user `{base_username}` already exists.",
            in_channel=False
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            return build_slack_response(f"❌ **AWS Error:** {e.response['Error']['Message']}", in_channel=False)

    # 4. Generate unique username and secure initial password
    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    username = f"{base_username}-{random_suffix}"
    password = generate_password()

    # 5. Provision IAM User, Console Password, Policies, and API Access Keys
    try:
        iam.create_user(UserName=username)
        iam.create_login_profile(UserName=username, Password=password, PasswordResetRequired=True)
        iam.attach_user_policy(UserName=username, PolicyArn="arn:aws:iam::aws:policy/AdministratorAccess")
        
        access_key_res = iam.create_access_key(UserName=username)
        access_key_id = access_key_res["AccessKey"]["AccessKeyId"]
        secret_access_key = access_key_res["AccessKey"]["SecretAccessKey"]
    except ClientError as e:
        return build_slack_response(f"❌ **IAM Provisioning Failed:** {e.response['Error']['Message']}", in_channel=False)

    # 6. Log creation audit record in DynamoDB
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        table.put_item(
            Item={
                "UserID": username,
                "Status": "ACTIVE",
                "Timestamp": timestamp,
                "Action": "CREATE_USER",
                "CreatedBy": created_by,
                "TargetEmail": email,
                "AccessKeyId": access_key_id
            }
        )
    except Exception as e:
        print(f"DynamoDB Audit Log Warning: {str(e)}")

    # 7. Dispatch welcome credentials via SES
    html_body = f"""
    <html><body>
    <h2>Welcome to AWS</h2>
    <p>Your IAM account has been provisioned.</p>
    <p><b>Username:</b> {username}<br><b>Password:</b> {password}</p>
    <p><b>Access Key ID:</b> {access_key_id}<br><b>Secret Access Key:</b> {secret_access_key}</p>
    </body></html>
    """

    try:
        ses.send_email(
            Source="sujithagrp@gmail.com",
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": "Welcome to AWS - Credentials"},
                "Body": {"Html": {"Data": html_body}}
            }
        )
    except ClientError as e:
        return build_slack_response(f"⚠️ User created as `{username}`, but SES email failed: {e.response['Error']['Message']}", in_channel=True)

    return build_slack_response(
        f"✅ **IAM User Created Successfully!**\n\n"
        f"• **Username:** `{username}`\n"
        f"• **Target Email:** `{email}`\n"
        f"• **Created By:** `{created_by}`\n\n"
        f"✉️ *Credentials emailed to {email}.*",
        in_channel=True
    )
