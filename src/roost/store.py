"""Platform memory (DynamoDB) and publishing (S3). App-agnostic.

Every app gets its own table and bucket (one isolated stack per app), so there
are no per-app prefixes here. The adapter owns what the pages say; the platform
owns getting records into memory and bytes onto the web.
"""

from decimal import Decimal

import boto3

_ddb = boto3.resource("dynamodb")
_s3 = boto3.client("s3")


def history(table_name: str, limit: int = 90) -> list:
    """Past records, newest first. Tables are small, so a scan is fine."""
    table = _ddb.Table(table_name)
    items = table.scan().get("Items", [])
    items.sort(key=lambda r: str(r.get("id", "")), reverse=True)
    return items[:limit]


def save(table_name: str, record: dict) -> None:
    if not str(record.get("id", "")).strip():
        raise ValueError("record needs a non-empty string 'id'")
    table = _ddb.Table(table_name)
    table.put_item(Item=_to_ddb(record))


def publish(bucket: str, pages: dict) -> str:
    """Write each {relative_path: content} to the bucket; return the site URL."""
    for rel, body in pages.items():
        ctype = "application/json" if rel.endswith(".json") else "text/html; charset=utf-8"
        _s3.put_object(Bucket=bucket, Key=rel, Body=body.encode("utf-8"), ContentType=ctype)
    region = _s3.get_bucket_location(Bucket=bucket).get("LocationConstraint") or "us-east-1"
    return f"http://{bucket}.s3-website-{region}.amazonaws.com"


def _to_ddb(obj):
    """DynamoDB rejects floats; store them as Decimal. Read back with float()."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_ddb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_ddb(v) for v in obj]
    return obj
