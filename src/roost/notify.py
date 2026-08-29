"""Send an app's alert. SNS email keeps the platform Free-Tier simple.

Swap this for Slack/Discord/SES per app if you want a nicer channel; app.py only
calls send_alert().
"""

import boto3

_sns = boto3.client("sns")


def send_alert(topic_arn: str, subject: str, body: str) -> None:
    # SNS caps subject at 100 chars and rejects newlines in it.
    subject = subject.replace("\n", " ")[:100] or "Agent alert"
    _sns.publish(TopicArn=topic_arn, Subject=subject, Message=body)
