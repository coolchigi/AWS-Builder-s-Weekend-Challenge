"""Lambda entry point. One handler runs every Roost app.

The lifecycle is fixed and app-agnostic:
    1. remember  -> load this app's past records (DynamoDB)
    2. sense     -> adapter.collect(): weather, a live price, ...
    3. reason    -> adapter.reason(): turn context + memory into one record
    4. keep      -> save it, unless the adapter says it's a duplicate
    5. publish   -> adapter.pages() -> S3 site (always refreshed)
    6. alert     -> email via SNS, only when the adapter says it's noteworthy

Which app runs is chosen by the ADAPTER env var. Pass {"force": true} when
invoking to save + email even if it would normally be skipped (handy for demos).
"""

import json
import logging
import os

from adapters import load
from roost import notify, store

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    event = event or {}
    adapter = load(os.environ["ADAPTER"])
    table = os.environ["TABLE_NAME"]
    bucket = os.environ["BUCKET_NAME"]
    topic = os.environ["ALERT_TOPIC_ARN"]

    past = store.history(table, limit=90)
    ctx = adapter.collect()
    record = adapter.reason(ctx, past)
    if record is None:
        logger.info(json.dumps({"event": "noop", "adapter": adapter.slug}))
        return {"status": "noop"}

    force = bool(event.get("force"))
    fresh = force or not adapter.is_duplicate(record, past)
    noteworthy = adapter.is_noteworthy(record, past)  # compares against past only

    if fresh:
        store.save(table, record)

    history = [record, *past] if fresh else past
    url = store.publish(bucket, adapter.pages(record, history))

    alerted = False
    if fresh and (force or noteworthy):
        subject, body = adapter.email(record, url)
        notify.send_alert(topic, subject, body)
        alerted = True

    logger.info(json.dumps({
        "event": "done", "adapter": adapter.slug, "id": record["id"],
        "fresh": fresh, "alerted": alerted, "site": url,
    }))
    return {
        "status": "published" if fresh else "refreshed",
        "id": record["id"], "alerted": alerted, "site": url,
    }
