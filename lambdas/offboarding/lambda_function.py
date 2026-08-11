import json
import datetime
import urllib.parse
import base64
import boto3
from botocore.exceptions import ClientError

iam = boto3.client("iam")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("OnboardingAudit")


def build_slack_response(text, in_channel=False):
    """Formats JSON response expected by Slack Slash Commands."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "response_type": "in_channel" if in_channel else "ephemeral",
            "text": text
        })
    }


def cleanup_user_dependencies(username):
    """Strips keys, console profile, inline/managed policies, and group memberships."""
    # 1. Access Keys
    keys_res = iam.list_access_keys(UserName=username)
    for key in keys_res.get("AccessKeyMetadata", []):
        iam.delete_access_key(UserName=username, AccessKeyId=key["AccessKeyId"])

    # 2. Login Profile
    try:
        iam.delete_login_profile(UserName=username)
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise e

    # 3. Managed Policies
    attached_policies = iam.list_attached_user_policies(UserName=username).get("AttachedPolicies", [])
    for policy in attached_policies:
        iam.detach_user_policy(UserName=username, PolicyArn=policy["PolicyArn"])

    # 4. Inline Policies
    inline_policies = iam.list_user_policies(UserName=username).get("PolicyNames", [])
    for policy_name in inline_policies:
        iam.delete_user_policy(UserName=username, PolicyName=policy_name)

    # 5. Group Memberships
    groups = iam.list_groups_for_user(UserName=username).get("Groups", [])
    for group in groups:
        iam.remove_user_from_group(GroupName=group["GroupName"], UserName=username)


def lambda_handler(event, context):
    """Main entrypoint for processing /offboard slash commands from Slack."""
    raw_body = event.get("body", "") or ""
    if event.get("isBase64Encoded", False):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    parsed_body = urllib.parse.parse_qs(raw_body)
    text = parsed_body.get("text", [""])[0].strip()
    created_by = parsed_body.get("user_name", ["Slack User"])[0]

    parts = text.split()
    if not parts:
        return build_slack_response("⚠️ **Missing Username!** Usage: `/offboard <username>`", in_channel=False)

    target_username = parts[0].strip()

    # 1. Verify target user exists
    try:
        iam.get_user(UserName=target_username)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            return build_slack_response(f"❌ User `{target_username}` does not exist.", in_channel=False)
        return build_slack_response(f"❌ AWS Error: {e.response['Error']['Message']}", in_channel=False)

    # 2. Revoke permissions and attach AWSDenyAll
    try:
        cleanup_user_dependencies(target_username)
        iam.attach_user_policy(
            UserName=target_username,
            PolicyArn="arn:aws:iam::aws:policy/AWSDenyAll"
        )
    except ClientError as e:
        return build_slack_response(f"❌ Offboarding failed: {e.response['Error']['Message']}", in_channel=False)

    # 3. Compute 2-hour cooling period timestamp
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    offboarded_at = now_utc.isoformat()
    deletion_scheduled_at = (now_utc + datetime.timedelta(hours=2)).isoformat()

    # 4. Record TOMBSTONE status in DynamoDB
    try:
        table.update_item(
            Key={"UserID": target_username},
            UpdateExpression="SET #s = :status, OffboardedAt = :ts, OffboardedBy = :by, DeletionScheduledAt = :ds",
            ExpressionAttributeNames={"#s": "Status"},
            ExpressionAttributeValues={
                ":status": "TOMBSTONE",
                ":ts": offboarded_at,
                ":by": created_by,
                ":ds": deletion_scheduled_at
            }
        )
    except Exception as e:
        print(f"DynamoDB Update Error: {str(e)}")

    return build_slack_response(
        f"🔒 **User `{target_username}` Offboarded (Cooling Period Started)!**\n\n"
        f"• **Status:** Access revoked (`AWSDenyAll` attached, credentials stripped).\n"
        f"• **Scheduled Deletion:** `{deletion_scheduled_at}` (UTC)\n"
        f"• **Offboarded By:** `{created_by}`",
        in_channel=True
    )