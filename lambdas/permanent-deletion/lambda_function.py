import os
import datetime
import boto3
from botocore.exceptions import ClientError

iam = boto3.client("iam")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("OnboardingAudit")
ses = boto3.client("ses")

# Replace with your verified manager/notification email
MANAGER_EMAIL = "sujithagrp@gmail.com"

def cleanup_and_delete_iam_user(username):
    """Ensures all remaining policy attachments are cleaned up and deletes the IAM user."""
    # 1. Detach AWSDenyAll or any remaining policies
    attached_policies = iam.list_attached_user_policies(UserName=username).get("AttachedPolicies", [])
    for policy in attached_policies:
        iam.detach_user_policy(UserName=username, PolicyArn=policy["PolicyArn"])

    # 2. Delete inline policies (if any exist)
    inline_policies = iam.list_user_policies(UserName=username).get("PolicyNames", [])
    for policy_name in inline_policies:
        iam.delete_user_policy(UserName=username, PolicyName=policy_name)

    # 3. Remove user from groups
    groups = iam.list_groups_for_user(UserName=username).get("Groups", [])
    for group in groups:
        iam.remove_user_from_group(GroupName=group["GroupName"], UserName=username)

    # 4. Hard delete the IAM User
    iam.delete_user(UserName=username)

def lambda_handler(event, context):
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    current_time_str = now_utc.isoformat()
    print(f"=== Running Permanent Deletion Check at {current_time_str} ===")

    # Scan DynamoDB for users in TOMBSTONE status
    # Note: For production with high item counts, consider a Global Secondary Index (GSI) on 'Status'
    response = table.scan(
        FilterExpression="#s = :tombstone_status",
        ExpressionAttributeNames={"#s": "Status"},
        ExpressionAttributeValues={":tombstone_status": "TOMBSTONE"}
    )
    
    tombstoned_users = response.get("Items", [])
    print(f"Found {len(tombstoned_users)} users in TOMBSTONE status.")

    deleted_count = 0

    for user in tombstoned_users:
        user_id = user.get("UserID")
        deletion_scheduled_at_str = user.get("DeletionScheduledAt")

        if not deletion_scheduled_at_str:
            continue

        deletion_scheduled_at = datetime.datetime.fromisoformat(deletion_scheduled_at_str)

        # Check if cooling period has passed
        if deletion_scheduled_at <= now_utc:
            print(f"Processing permanent deletion for user: {user_id}")
            
            try:
                # 1. Permanently Delete from IAM
                cleanup_and_delete_iam_user(user_id)
                print(f"Successfully deleted IAM User: {user_id}")

                # 2. Update DynamoDB Status
                table.update_item(
                    Key={"UserID": user_id},
                    UpdateExpression="SET #s = :status, DeletedAt = :deleted_at",
                    ExpressionAttributeNames={"#s": "Status"},
                    ExpressionAttributeValues={
                        ":status": "DELETED_PERMANENTLY",
                        ":deleted_at": current_time_str
                    }
                )

                # 3. Send Notification Email to Manager
                email_subject = f"Permanent Deletion Completed: {user_id}"
                email_body = f"""
                <html><body>
                <h3>IAM User Permanent Deletion Notice</h3>
                <p>User <b>{user_id}</b> has been permanently deleted after completing the 2-hour cooling period.</p>
                <p><b>Scheduled Deletion Time:</b> {deletion_scheduled_at_str}<br>
                <b>Execution Time:</b> {current_time_str}</p>
                </body></html>
                """

                ses.send_email(
                    Source=MANAGER_EMAIL,
                    Destination={"ToAddresses": [MANAGER_EMAIL]},
                    Message={
                        "Subject": {"Data": email_subject},
                        "Body": {"Html": {"Data": email_body}}
                    }
                )
                deleted_count += 1

            except ClientError as e:
                print(f"Error permanently deleting user {user_id}: {e.response['Error']['Message']}")
            except Exception as e:
                print(f"Unexpected error for user {user_id}: {str(e)}")

    return {
        "statusCode": 200,
        "body": f"Successfully processed {deleted_count} permanent user deletions."
    }