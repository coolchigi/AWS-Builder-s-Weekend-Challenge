"""Send the agent's alert. SNS email keeps the scaffold Free-Tier simple.

Swap this for Slack/Discord/SES per challenge if you want a nicer demo, the
handler only calls send_alert().
"""

import boto3

_sns = boto3.client("sns")


def send_alert(topic_arn: str, subject: str, body: str) -> None:
    # SNS caps subject at 100 chars and rejects newlines in it.
    subject = subject.replace("\n", " ")[:100] or "Agent alert"
    _sns.publish(TopicArn=topic_arn, Subject=subject, Message=body)
