# 🚀 Zero-Touch AWS User Onboarding System

This project automates AWS IAM user onboarding using a completely serverless architecture.

The workflow is triggered from Slack and uses AWS Lambda, API Gateway, DynamoDB and Amazon SES to automate onboarding while maintaining an audit trail.

## Business Problem

In many organizations, onboarding new employees is a manual process.

Administrators need to:

- Create AWS users
- Record who created them
- Notify the employee
- Maintain audit logs

This process is repetitive, slow and prone to human error.

## Solution

This project automates the onboarding workflow using AWS serverless services.

Once an onboarding request is received:

- Validate the request
- Check whether the user already exists
- Create the IAM user
- Store an audit record in DynamoDB
- Send a welcome email
- Return a response to Slack

## Architecture

```text
Slack

↓

API Gateway

↓

AWS Lambda

├── IAM

├── DynamoDB

├── Amazon SES

↓

Slack Response
```

## Features

- Serverless Architecture
- Slack Integration
- IAM User Management
- DynamoDB Audit Logging
- Amazon SES Email Notification
- CloudWatch Logging
- Error Handling
- Input Validation

## Technologies Used

- AWS Lambda
- Amazon API Gateway
- AWS IAM
- Amazon DynamoDB
- Amazon SES
- Amazon CloudWatch
- Python
- boto3
- Slack
- Git
- GitHub

## Project Structure

```text
ZeroTouchOnboarding/

│

├── lambda_function.py

├── README.md

├── requirements.txt

├── docs/

├── sample-events/

└── screenshots/
```

## Future Enhancements

- Infrastructure as Code using Terraform or AWS SAM
- Approval workflow before user creation
- Multiple IAM groups based on department
- Integration with HR systems
- Microsoft Teams support

## Author

Sujitha E

AWS | Python | DevOps Enthusiast