"""Lambda entry point for the Daily Lexicon creative agent.

Flow (runs on a schedule, no human in the loop):
    1. remember  -> load words already used, so we never repeat (task memory)
    2. sense     -> today's date, season, and weather (task.collect)
    3. create    -> Bedrock conjures a new word packet (agent.analyze)
    4. keep      -> store the new word in DynamoDB
    5. publish   -> render today's page + archive to S3
    6. deliver   -> email the word via SNS

Only task.py holds the creative concept. Swap it to re-skin the agent.
"""

import json
import os

from agent import analyze
from notify import send_alert
import store
import task


def handler(event, context):
    table = os.environ["TABLE_NAME"]
    bucket = os.environ["BUCKET_NAME"]

    # 1. What has the agent already taught? (drives non-repetition + evolution)
    history = store.recent_words(table, limit=60)
    used = [row["word"] for row in history]

    # 2. Sense the day so the word can be themed to it.
    ctx = task.collect()

    # 3. Create today's word packet.
    packet = analyze(
        model_id=os.environ["MODEL_ID"],
        system_prompt=task.SYSTEM_PROMPT,
        user_prompt=task.build_prompt(ctx, used),
    )
    packet["date"] = ctx["date"]

    # 4. Remember it.
    store.save_word(table, packet)

    # 5. Publish the viewable artifact (today + a growing archive).
    all_words = [packet] + history
    site_url = store.publish_site(bucket, packet, all_words)

    # 6. Deliver it to your inbox.
    send_alert(
        topic_arn=os.environ["ALERT_TOPIC_ARN"],
        subject=f"Today's word: {packet['word']}",
        body=task.render_email(packet, site_url),
    )

    print(json.dumps({"published": packet["word"], "site": site_url}))
    return {"published": packet["word"], "site": site_url}
