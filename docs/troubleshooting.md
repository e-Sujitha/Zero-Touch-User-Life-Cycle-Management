# Troubleshooting Guide

This document records common issues encountered while developing and testing the IAM lifecycle automation system and the approach used to troubleshoot them.

---

## 1. Lambda Syntax or Indentation Error

### Symptom

Lambda execution fails before the function can complete.

Example:

```text
SyntaxError: unexpected indent
```

### Possible Cause

Python indentation is inconsistent within the Lambda function.

### Troubleshooting

1. Open the Lambda function in the AWS Console.
2. Review the line mentioned in the error message.
3. Check indentation around `if`, `else`, `try`, `except`, and function blocks.
4. Ensure the code uses consistent spaces.
5. Deploy the updated function.
6. Run the test event again.

### Lesson

Python is indentation-sensitive, so formatting errors can prevent the Lambda function from being executed at all.

---

# 2. DynamoDB Missing Key Error

### Symptom

The Lambda function creates the IAM user successfully but fails when writing the audit record.

Example:

```text
ValidationException:
Missing the key UserID in the item
```

### Possible Cause

The DynamoDB table expects a partition key with a specific name, but the Lambda function sends a different attribute name.

For example:

```text
Table Key:
UserID
```

while the Lambda sends:

```text
UserId
```

### Troubleshooting

Check the DynamoDB table schema and ensure that the attribute name used by the Lambda exactly matches the partition key.

Example:

```python
item = {
    "UserID": username,
    "Timestamp": timestamp,
    "Action": "CREATE_USER"
}
```

### Lesson

DynamoDB key names are case-sensitive. The application schema and Lambda code must use the exact same attribute names.

---

# 3. SES Message Rejected

### Symptom

The Lambda function completes most of the workflow but Amazon SES rejects the email.

Example:

```text
MessageRejected:
Email address is not verified
```

### Possible Cause

The sender or recipient email address has not been verified in the SES environment being used.

### Troubleshooting

1. Open Amazon SES.
2. Check the verified identities.
3. Confirm that the sender email address is verified.
4. If SES is operating in a restricted/sandbox environment, verify the recipient address as required.
5. Confirm that the Lambda function is using the same AWS Region where the SES identity is configured.
6. Test the email workflow again.

### Lesson

AWS services can have Region-specific configuration. Always verify that the resource and application are operating in the expected Region.

---

# 4. IAM AccessDenied Error

### Symptom

The Lambda function runs but an IAM API operation fails with an access-denied error.

Example:

```text
AccessDenied
```

### Possible Cause

The Lambda execution role does not have permission to perform the requested IAM operation.

### Troubleshooting

1. Open IAM.
2. Locate the Lambda execution role.
3. Review its attached policies.
4. Identify the exact AWS API operation that failed.
5. Add only the required permission.
6. Run the Lambda test again.

Example permissions may include:

```text
iam:GetUser
iam:CreateUser
iam:CreateAccessKey
iam:DeleteAccessKey
iam:DeleteUser
iam:AttachUserPolicy
iam:DetachUserPolicy
```

Only grant permissions required by the specific Lambda function.

### Lesson

An AccessDenied error is often a useful indication that the IAM policy needs to be reviewed rather than simply granting broad administrative permissions.

---

# 5. Slack Request Not Reaching Lambda

### Symptom

The Slack slash command is executed, but no successful response is returned.

### Troubleshooting

Check the request path in order:

```text
Slack
  ↓
API Gateway
  ↓
Lambda
  ↓
AWS Services
```

Verify:

1. Slack slash command Request URL.
2. API Gateway endpoint.
3. HTTP method.
4. API deployment/stage.
5. Lambda integration.
6. Lambda execution logs.
7. API Gateway logs if enabled.

CloudWatch Logs can help determine whether the request reached Lambda.

---

# 6. Lambda Timeout

### Symptom

The Lambda function starts but does not complete within the configured timeout.

### Troubleshooting

Review CloudWatch Logs and identify the last operation executed.

Potential areas to investigate:

* IAM API calls
* DynamoDB operations
* SES operations
* Network-related operations
* Unexpected loops
* Retry behavior

Increase the timeout only when necessary. The preferred approach is to identify and resolve the underlying cause.

---

# 7. User Already Exists

### Symptom

An onboarding request fails because an IAM user with the requested name already exists.

### Recommended Handling

The onboarding Lambda should check whether the user exists before attempting to create it.

Conceptually:

```text
Receive username
      ↓
Check IAM
      ↓
Does user exist?
   /          \
 Yes           No
  ↓             ↓
Return error   Create user
```

This prevents unnecessary API failures and makes the workflow more predictable.

---

# Troubleshooting Approach

The general troubleshooting process used in this project is:

```text
1. Reproduce the problem
        ↓
2. Read the exact error
        ↓
3. Check CloudWatch Logs
        ↓
4. Identify the AWS service involved
        ↓
5. Verify configuration
        ↓
6. Verify IAM permissions
        ↓
7. Fix the root cause
        ↓
8. Test again
        ↓
9. Document the solution
```

This approach helps avoid making random configuration changes and focuses on identifying the actual cause of a failure.
