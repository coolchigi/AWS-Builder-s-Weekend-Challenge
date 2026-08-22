"""Lambda entry point for the Daily Lexicon creative agent.

Flow (scheduled, no human in the loop):
    1. remember  -> load words already used (task memory in DynamoDB)
    2. sense     -> today's date, season, and weather
    3. guard     -> if today's word already exists, re-publish and stop (idempotent)
    4. create    -> Bedrock conjures a validated word packet
    5. keep      -> store the new word
    6. publish   -> render today's page + archive to S3
    7. deliver   -> email the word via SNS

Only task.py holds the creative concept. Swap it to re-skin the agent.
"""

import json
import logging
import os

from agent import analyze
from notify import send_alert
import store
import task

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    event = event or {}
    table = os.environ["TABLE_NAME"]
    bucket = os.environ["BUCKET_NAME"]

    history = store.recent_words(table, limit=60)
    ctx = task.collect()
    logger.info(json.dumps({
        "event": "start", "date": ctx["date"],
        "known_words": len(history), "weather": ctx["weather"],
    }))

    # Idempotency: one word per day. Re-running just refreshes the page and
    # exits, so a retry or a double-fire never emails you twice. Pass
    # {"force": true} when invoking to override for testing.
    existing = next((w for w in history if w.get("date") == ctx["date"]), None)
    if existing and not event.get("force"):
        today = {**existing, "word": existing.get("display_word", existing["word"])}
        site_url = store.publish_site(bucket, today, history)
        logger.info(json.dumps({"event": "skip_duplicate", "word": today["word"], "site": site_url}))
        return {"status": "already_done", "word": today["word"], "site": site_url}

    # Create today's word.
    used = [w["word"] for w in history]
    packet = analyze(
        model_id=os.environ["MODEL_ID"],
        system_prompt=task.SYSTEM_PROMPT,
        user_prompt=task.build_prompt(ctx, used),
    )
    packet["date"] = ctx["date"]

    store.save_word(table, packet)
    site_url = store.publish_site(bucket, packet, [packet] + history)
    send_alert(
        topic_arn=os.environ["ALERT_TOPIC_ARN"],
        subject=f"Today's word: {packet['word']}",
        body=task.render_email(packet, site_url),
    )

    logger.info(json.dumps({"event": "published", "word": packet["word"], "site": site_url}))
    return {"status": "published", "word": packet["word"], "site": site_url}
