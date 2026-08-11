# Business Case

## Problem

Managing employee IAM access manually can become inefficient as an organization grows.

A typical process may require an administrator to:

1. Receive an onboarding or offboarding request.
2. Open the AWS Console.
3. Create or locate the IAM user.
4. Configure permissions.
5. Generate credentials.
6. Send credentials to the employee.
7. Remove access during offboarding.
8. Maintain records of the changes.

Performing these tasks repeatedly increases operational effort and creates opportunities for human error.

---

# Proposed Solution

The Zero-Touch IAM User Lifecycle Management System automates these operations through Slack-based ChatOps.

Administrators can initiate lifecycle operations using simple commands:

```text
/onboard
/offboard
/restore
```

The request is processed by AWS Lambda and the required AWS services are automatically invoked.

---

# Business Benefits

## Faster Onboarding

New users can be provisioned through an automated workflow rather than requiring every step to be performed manually.

This can reduce the time required to provide initial access and allows employees to become productive sooner.

---

## Safer Offboarding

The system removes active access keys and applies an explicit deny policy during offboarding.

This reduces the risk of forgotten credentials remaining active after an employee leaves the organization.

---

## Reduced Manual Work

Repeated administrative operations are handled by Lambda functions.

This allows cloud administrators to spend more time on higher-value infrastructure and security tasks.

---

## Improved Auditability

Lifecycle events are stored in DynamoDB.

Administrators can use these records to understand:

* Who was onboarded
* Who was offboarded
* When an action occurred
* Current lifecycle state
* When permanent deletion is scheduled
* Whether a user was restored

---

## Controlled Recovery

Instead of immediately deleting an offboarded user, the system uses a temporary TOMBSTONE state.

This creates a controlled recovery window in which access can be restored if the offboarding request was incorrect or needs to be reversed.

---

# Security Improvements

The architecture incorporates several security-focused controls:

* Least-privilege IAM permissions
* Immediate access revocation
* Explicit deny policy during quarantine
* Credential delivery through Amazon SES
* Centralized audit records
* Controlled permanent deletion
* CloudWatch logging

---

# Why Serverless?

The project uses AWS managed services instead of maintaining dedicated servers.

This provides:

* No server maintenance
* Automatic scaling
* Event-driven execution
* Reduced infrastructure management
* Pay-per-use architecture

For an IAM automation workflow that runs only when an administrator performs an operation or when a scheduled cleanup is triggered, a serverless architecture is a practical design choice.

---

# Potential Production Improvements

For a production enterprise implementation, additional controls could be introduced:

* AWS IAM Identity Center instead of individual IAM users
* Infrastructure as Code using Terraform or AWS CDK
* Multi-account AWS Organizations integration
* Slack approval workflows
* Centralized security monitoring
* Automated testing and CI/CD
* Additional authentication and request validation
* Formal incident and audit workflows

The current project provides a foundation for extending IAM lifecycle automation into a broader cloud governance platform.
