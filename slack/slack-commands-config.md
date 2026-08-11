# Slack App Slash Commands Setup

## Commands Configuration

| Command | Request URL | Usage Example | Description |
| :--- | :--- | :--- | :--- |
| `/onboard` | `https://bovnithi1l.execute-api.ap-south-2.amazonaws.com/prod/onboard` | `/onboard john john@gmail.com` | Provisions IAM user, access keys, console login, attaches AdministratorAccess, and sends welcome email via SES. |
| `/offboard` | `https://bovnithi1l.execute-api.ap-south-2.amazonaws.com/prod/offboard` | `/offboard john-a1b2c3` | Strips all credentials, attaches AWSDenyAll, sets status to TOMBSTONE, and starts 2-hour cooling window. |
| `/restore` | `https://bovnithi1l.execute-api.ap-south-2.amazonaws.com/prod/restore` | `/restore john-a1b2c3` | Detaches AWSDenyAll, generates new access keys, restores status to ACTIVE, and emails new credentials. |