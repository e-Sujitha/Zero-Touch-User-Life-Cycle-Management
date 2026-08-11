import json
import datetime
import urllib.parse
import base64
import boto3
from botocore.exceptions import ClientError

# Initialize AWS Service Clients
iam = boto3.client("iam")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("OnboardingAudit")
ses = boto3.client("ses")

# Verified SES Email address for administrative notifications
ADMIN_EMAIL = "sujithagrp@gmail.com"


def build_slack_response(text, in_channel=False):
    """Formats JSON response structure expected by Slack Slash Commands."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "response_type": "in_channel" if in_channel else "ephemeral",
            "text": text
        })
    }


def handle_restore(text, restored_by):
    """
    Core restoration logic:
    1. Validates TOMBSTONE status and cooling period in DynamoDB.
    2. Detaches AWSDenyAll policy from the IAM user.
    3. Issues new programmatic access keys.
    4. Updates DynamoDB state to ACTIVE.
    5. Sends confirmation emails via SES to both user and manager.
    """
    parts = text.split()
    if not parts:
        return build_slack_response(
            "⚠️ **Missing Username!**\nUsage: `/restore <username>`\n*Example:* `/restore raj-a1b2c3`",
            in_channel=False
        )

    target_username = parts[0].strip()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    current_time_str = now_utc.isoformat()

    # Step 1: Query DynamoDB record for the target user
    try:
        response = table.get_item(Key={"UserID": target_username})
        user_item = response.get("Item")
    except Exception as e:
        return build_slack_response(f"❌ **Database Error:** {str(e)}", in_channel=False)

    if not user_item:
        return build_slack_response(f"❌ **Restore Failed:** User `{target_username}` not found in record system.", in_channel=False)

    # Step 2: Validate TOMBSTONE status and cooling period
    status = user_item.get("Status")
    deletion_scheduled_at_str = user_item.get("DeletionScheduledAt")
    user_email = user_item.get("TargetEmail") or ADMIN_EMAIL

    if status != "TOMBSTONE" or not deletion_scheduled_at_str:
        return build_slack_response(
            f"❌ **Restore Aborted:** User `{target_username}` is not in tombstone state or has already been restored.",
            in_channel=False
        )

    deletion_scheduled_at = datetime.datetime.fromisoformat(deletion_scheduled_at_str)

    # Check if cooling period expired
    if now_utc >= deletion_scheduled_at:
        return build_slack_response(
            f"❌ **Restore Aborted:** Cooling period for `{target_username}` expired. Scheduled deletion has passed.",
            in_channel=False
        )

    # Step 3: Remove AWSDenyAll Policy & Issue New Access Key
    try:
        # Detach explicit Deny policy
        iam.detach_user_policy(
            UserName=target_username,
            PolicyArn="arn:aws:iam::aws:policy/AWSDenyAll"
        )

        # Generate new credentials for the restored account
        access_key_res = iam.create_access_key(UserName=target_username)
        new_access_key_id = access_key_res["AccessKey"]["AccessKeyId"]
        new_secret_access_key = access_key_res["AccessKey"]["SecretAccessKey"]

    except ClientError as e:
        return build_slack_response(f"❌ **IAM Restoration Failed:** {e.response['Error']['Message']}", in_channel=False)

    # Step 4: Update DynamoDB status to ACTIVE
    try:
        table.update_item(
            Key={"UserID": target_username},
            UpdateExpression="SET #s = :status, RestoredAt = :ra, RestoredBy = :rb REMOVE DeletionScheduledAt",
            ExpressionAttributeNames={"#s": "Status"},
            ExpressionAttributeValues={
                ":status": "ACTIVE",
                ":ra": current_time_str,
                ":rb": restored_by
            }
        )
    except Exception as e:
        print(f"DynamoDB Update Error during restore: {str(e)}")

    # Step 5: Send SES Email Notifications
    # Email to User with new API key
    user_html_body = f"""
    <html><body>
    <h2>AWS Access Restored</h2>
    <p>Your AWS account (<b>{target_username}</b>) has been restored successfully.</p>
    <p><b>New Access Key ID:</b> {new_access_key_id}<br>
    <b>New Secret Access Key:</b> {new_secret_access_key}</p>
    <p>Please re-configure your CLI or tools with these credentials.</p>
    </body></html>
    """

    # Email to Manager
    manager_html_body = f"""
    <html><body>
    <h3>Account Restoration Notice</h3>
    <p>User account <b>{target_username}</b> was restored successfully within the 2-hour cooling window.</p>
    <p><b>Restored By:</b> {restored_by}<br>
    <b>Restored At:</b> {current_time_str}</p>
    </body></html>
    """

    try:
        # User notification
        ses.send_email(
            Source=ADMIN_EMAIL,
            Destination={"ToAddresses": [user_email]},
            Message={
                "Subject": {"Data": "AWS Account Restored - New Credentials"},
                "Body": {"Html": {"Data": user_html_body}}
            }
        )

        # Manager notification
        ses.send_email(
            Source=ADMIN_EMAIL,
            Destination={"ToAddresses": [ADMIN_EMAIL]},
            Message={
                "Subject": {"Data": f"Restoration Notice: {target_username}"},
                "Body": {"Html": {"Data": manager_html_body}}
            }
        )
    except ClientError as e:
        print(f"SES Notification Warning: {e.response['Error']['Message']}")

    # Step 6: Return Slack Confirmation
    return build_slack_response(
        f"✅ **Account Restored Successfully!**\n\n"
        f"• **User:** `{target_username}`\n"
        f"• **Status:** Restored (`AWSDenyAll` removed, fresh access keys created).\n"
        f"• **Restored By:** `{restored_by}`\n"
        f"• **Notifications:** Sent to user (`{user_email}`) and manager.",
        in_channel=True
    )


def lambda_handler(event, context):
    """Main Lambda entrypoint for handling Slack /restore command requests."""
    print("=== [Restore Lambda] Processing Incoming Request ===")

    raw_body = event.get("body", "") or ""
    if event.get("isBase64Encoded", False):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    parsed_body = urllib.parse.parse_qs(raw_body)
    
    text = parsed_body.get("text", [""])[0].strip()
    restored_by = parsed_body.get("user_name", ["Slack User"])[0]

    return handle_restore(text, restored_by)