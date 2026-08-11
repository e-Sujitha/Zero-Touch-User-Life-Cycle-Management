
# Import AWS SDK and Python libraries used by the Lambda function
import json
import random
import string
import datetime
import urllib.parse
import base64
import boto3
from botocore.exceptions import ClientError

# Create AWS service clients.
# These clients allow the Lambda function to communicate with AWS services.
iam = boto3.client("iam")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("OnboardingAudit")
ses = boto3.client("ses")

# Generates a random password that satisfies the IAM password policy.
# The password contains uppercase letters, lowercase letters,
# numbers, and special characters.

def generate_password(length=16):

    # Allowed characters that can be used while generating the password.
    characters = string.ascii_letters + string.digits + "!@#$%^&*()"
    # Keep generating passwords until one satisfies the password policy.
    while True:
        # Randomly pick characters to create a password.
        password = "".join(random.choice(characters) for _ in range(length))
        # Check whether the password has all required character types.
        if (
            any(c.isupper() for c in password)
            and any(c.islower() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*()" for c in password)
        ):
        # Return the generated password once it meets all requirements.
            return password

def build_slack_response(text, in_channel=False):
    """Helper that guarantees Slack receives a valid 200 OK JSON response."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "response_type": "in_channel" if in_channel else "ephemeral",
            "text": text
        })
    }

# Main entry point of the Lambda function.
# This function receives the request,
# processes it,
# communicates with AWS services,
# and returns the final response.

def lambda_handler(event, context):
    print("=== [STEP 1] Received event trigger from API Gateway ===")
    
    # Extract body safely
    raw_body = event.get("body", "") or ""
    if event.get("isBase64Encoded", False):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    # Read and parse the incoming Slack request.
    parsed_body = urllib.parse.parse_qs(raw_body)
    print(f"DEBUG: Parsed Slack payload keys: {list(parsed_body.keys())}")

    # Extract text parameter
    text_list = parsed_body.get("text", [])
    text = text_list[0].strip() if text_list else ""
    user_name_list = parsed_body.get("user_name", [])
    created_by = user_name_list[0] if user_name_list else "Slack User"

    # --- SCENARIO 1: Empty text provided (/onboard) ---
    if not text:
        print("⚠️ Handling Scenario 1: Empty command text submitted.")
        return build_slack_response(
            "⚠️ **Missing Arguments!**\nUsage: `/onboard <username> <email>`\n*Example:* `/onboard raj raj@gmail.com`",
            in_channel=False
        )

    # --- SCENARIO 2: Incomplete text provided (/onboard john) ---
    parts = text.split()
    if len(parts) < 2:
        print(f"⚠️ Handling Scenario 2: Incomplete command parameters '{text}'.")
        return build_slack_response(
            "⚠️ **Invalid Usage!** Please provide both username and email.\n*Example:* `/onboard raj raj@gmail.com`",
            in_channel=False
        )

    base_username = parts[0].lower()
    email = parts[1]

    # --- SCENARIO 3: Check if IAM user already exists ---
    print(f"=== [STEP 3] Checking if IAM user '{base_username}' already exists ===")
    try:
        iam.get_user(UserName=base_username)
        print(f"⚠️ User '{base_username}' already exists.")
        return build_slack_response(
            f"❌ **User Creation Aborted:** The IAM username `{base_username}` already exists in AWS.",
            in_channel=False
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print(f"✅ User '{base_username}' does not exist. Proceeding with creation.")
        else:
            return build_slack_response(f"❌ **AWS Error:** {e.response['Error']['Message']}", in_channel=False)

    # --- SCENARIO 4: Full Creation Flow ---
    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    username = f"{base_username}-{random_suffix}"
    # Generate a secure temporary password for the new user.
    password = generate_password()

    try:
        # Create a new IAM user in AWS.
        iam.create_user(UserName=username)
        # Create a console login password for the IAM user.
        iam.create_login_profile(UserName=username, Password=password, PasswordResetRequired=True)
        # Attach the required IAM policy to the user.
        iam.attach_user_policy(UserName=username, PolicyArn="arn:aws:iam::aws:policy/AdministratorAccess")
        # Generate programmatic access credentials for the user.
        access_key_res = iam.create_access_key(UserName=username)
        access_key_id = access_key_res["AccessKey"]["AccessKeyId"]
        secret_access_key = access_key_res["AccessKey"]["SecretAccessKey"]
    except ClientError as e:
        return build_slack_response(f"❌ **IAM Provisioning Failed:** {e.response['Error']['Message']}", in_channel=False)

    # DynamoDB Audit Log
    try:
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Store an audit record in DynamoDB for tracking user onboarding.
        table.put_item(
            Item={
                "UserID": username,
                "Timestamp": timestamp,
                "Action": "CREATE_USER",
                "CreatedBy": created_by,
                "TargetEmail": email,
                "AccessKeyId": access_key_id
            }
        )
    except Exception as e:
        print(f"DynamoDB Log Warning: {str(e)}")

    # Create the HTML email that will be sent to the user.
    html_body = f"""
    <html><body>
    <h2>Welcome to AWS</h2>
    <p>Your IAM account has been created.</p>
    <p><b>Username:</b> {username}<br><b>Password:</b> {password}</p>
    <p><b>Access Key ID:</b> {access_key_id}<br><b>Secret Access Key:</b> {secret_access_key}</p>
    </body></html>
    """

    try:
        # Send the welcome email using Amazon SES.
        ses.send_email(
            Source="sujithagrp@gmail.com",
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": "Welcome to AWS - Credentials"},
                "Body": {"Html": {"Data": html_body}}
            }
        )
    except ClientError as e:
        return build_slack_response(f"⚠️ User created as `{username}`, but SES Email failed: {e.response['Error']['Message']}", in_channel=True)

    # Return a success response after all operations complete successfully.
    return build_slack_response(
        f"✅ **IAM User Created Successfully!**\n\n"
        f"• **Username:** `{username}`\n"
        f"• **Target Email:** `{email}`\n"
        f"• **Created By:** `{created_by}`\n\n"
        f"✉️ *Credentials emailed to {email}.*",
        in_channel=True
    )