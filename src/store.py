"""Memory (DynamoDB) and the published artifact (S3 static site).

The table gives the agent a memory so it never repeats a word and can evolve.
The site is the thing "waiting for you when you return" - a page with today's
word and a growing archive.
"""

import html
import json

import boto3

_ddb = boto3.resource("dynamodb")
_s3 = boto3.client("s3")


def recent_words(table_name: str, limit: int = 60) -> list:
    """Return past word packets, newest first. Small table, a scan is fine."""
    table = _ddb.Table(table_name)
    items = table.scan().get("Items", [])
    items.sort(key=lambda r: r.get("date", ""), reverse=True)
    return items[:limit]


def save_word(table_name: str, packet: dict) -> None:
    table = _ddb.Table(table_name)
    # Key on the lowercased word so a repeat can never be stored twice.
    item = dict(packet)
    item["word"] = packet["word"].strip().lower()
    item["display_word"] = packet["word"].strip()
    table.put_item(Item=item)


def publish_site(bucket: str, today: dict, archive: list) -> str:
    """Write today's JSON feed and the rendered HTML page to S3."""
    _s3.put_object(
        Bucket=bucket,
        Key="today.json",
        Body=json.dumps(today, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    _s3.put_object(
        Bucket=bucket,
        Key="index.html",
        Body=_render_html(today, archive).encode("utf-8"),
        ContentType="text/html; charset=utf-8",
    )
    location = _s3.get_bucket_location(Bucket=bucket).get("LocationConstraint")
    region = location or "us-east-1"
    return f"http://{bucket}.s3-website-{region}.amazonaws.com"


def _render_html(today: dict, archive: list) -> str:
    def esc(key, default=""):
        return html.escape(str(today.get(key, default)))

    poem = html.escape(today.get("poem", "")).replace("\n", "<br>")

    archive_rows = "\n".join(
        f'<li><b>{html.escape(str(r.get("display_word", r.get("word", ""))))}</b>'
        f' <span class="dim">&mdash; {html.escape(str(r.get("definition", "")))}</span></li>'
        for r in archive[1:41]
    ) or '<li class="dim">The archive begins today.</li>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Lexicon</title>
<style>
  :root {{ --bg:#faf7f0; --ink:#211d17; --dim:#8a8172; --card:#fffdf8; --line:#e7e0d2; --accent:#9a5b2e; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#1a1712; --ink:#f0e9db; --dim:#a79c88; --card:#231f19; --line:#3a342a; --accent:#e0a066; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font-family:Georgia,'Iowan Old Style',serif; line-height:1.6; }}
  .wrap {{ max-width:640px; margin:0 auto; padding:48px 22px 80px; }}
  .kicker {{ text-transform:uppercase; letter-spacing:.18em; font-size:.72rem;
    color:var(--dim); font-family:system-ui,sans-serif; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px;
    padding:34px; margin-top:14px; }}
  .word {{ font-size:2.7rem; margin:.1em 0 0; }}
  .pron {{ color:var(--dim); font-style:italic; }}
  .pos {{ color:var(--accent); font-family:system-ui,sans-serif; font-size:.85rem;
    text-transform:uppercase; letter-spacing:.08em; margin-top:6px; }}
  .def {{ font-size:1.2rem; margin:18px 0; }}
  .label {{ font-family:system-ui,sans-serif; font-size:.7rem; text-transform:uppercase;
    letter-spacing:.12em; color:var(--dim); margin-top:22px; }}
  .poem {{ font-style:italic; border-left:3px solid var(--accent); padding-left:16px; }}
  .theme {{ color:var(--dim); font-size:.9rem; margin-top:24px; }}
  h2 {{ font-size:1rem; letter-spacing:.06em; margin:48px 0 8px; }}
  ul {{ list-style:none; padding:0; }} li {{ padding:7px 0; border-bottom:1px solid var(--line); }}
  .dim {{ color:var(--dim); }}
  footer {{ margin-top:40px; color:var(--dim); font-size:.8rem;
    font-family:system-ui,sans-serif; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="kicker">Daily Lexicon &middot; {esc('date')}</div>
    <div class="card">
      <h1 class="word">{esc('word')}</h1>
      <div class="pron">{esc('pronunciation')}</div>
      <div class="pos">{esc('part_of_speech')}</div>
      <p class="def">{esc('definition')}</p>
      <div class="label">Origin</div>
      <div>{esc('etymology')}</div>
      <div class="label">In a sentence</div>
      <div>&ldquo;{esc('example_sentence')}&rdquo;</div>
      <div class="label">Today's verse</div>
      <p class="poem">{poem}</p>
      <div class="theme">{esc('theme_note')}</div>
    </div>
    <h2>The archive</h2>
    <ul>{archive_rows}</ul>
    <footer>Made each morning by an always-on agent &middot; Amazon Bedrock &middot; Lambda &middot; EventBridge</footer>
  </div>
</body>
</html>"""
