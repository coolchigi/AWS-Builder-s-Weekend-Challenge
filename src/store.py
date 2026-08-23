"""Memory (DynamoDB) and the published artifact (S3 static site).

The table gives the agent a memory so it never repeats a word and can evolve.
The site is what's waiting when you return: today's word on the front page, every
past word as its own page, and a browsable archive that links them together.
"""

import html
import json
import re

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
    item = dict(packet)
    item["word"] = packet["word"].strip().lower()
    item["display_word"] = packet["word"].strip()
    table.put_item(Item=item)


def publish_site(bucket: str, today: dict, archive: list) -> str:
    """Write the front page, today's own word page, the JSON feed, and archive."""
    _put(bucket, "today.json", json.dumps(today, ensure_ascii=False), "application/json")
    _put(bucket, "index.html", _render_index(today, archive), "text/html; charset=utf-8")
    _put(bucket, "archive.html", _render_archive(archive), "text/html; charset=utf-8")

    # Write a page for today plus every past word, so every archive link resolves
    # (older words predate per-word pages, so we backfill them here).
    seen = set()
    for row in [today] + archive:
        slug = _slug(row)
        if slug not in seen:
            seen.add(slug)
            _put(bucket, f"words/{slug}.html", _render_word_page(row), "text/html; charset=utf-8")

    location = _s3.get_bucket_location(Bucket=bucket).get("LocationConstraint")
    region = location or "us-east-1"
    return f"http://{bucket}.s3-website-{region}.amazonaws.com"


def _put(bucket: str, key: str, body: str, content_type: str) -> None:
    _s3.put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"), ContentType=content_type)


def _slug(row: dict) -> str:
    word = str(row.get("display_word", row.get("word", ""))).lower()
    return re.sub(r"[^a-z0-9]+", "-", word).strip("-") or "word"


# --- rendering -------------------------------------------------------------

_CSS = """
  :root { --bg:#faf7f0; --ink:#211d17; --dim:#8a8172; --card:#fffdf8; --line:#e7e0d2; --accent:#9a5b2e; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#1a1712; --ink:#f0e9db; --dim:#a79c88; --card:#231f19; --line:#3a342a; --accent:#e0a066; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
    font-family:Georgia,'Iowan Old Style',serif; line-height:1.6; }
  a { color:var(--accent); text-decoration:none; }
  a:hover { text-decoration:underline; }
  .wrap { max-width:640px; margin:0 auto; padding:48px 22px 80px; }
  .kicker { text-transform:uppercase; letter-spacing:.18em; font-size:.72rem;
    color:var(--dim); font-family:system-ui,sans-serif; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:14px;
    padding:34px; margin-top:14px; }
  .word { font-size:2.7rem; margin:.1em 0 0; }
  .pron { color:var(--dim); font-style:italic; }
  .pos { color:var(--accent); font-family:system-ui,sans-serif; font-size:.85rem;
    text-transform:uppercase; letter-spacing:.08em; margin-top:6px; }
  .def { font-size:1.2rem; margin:18px 0; }
  .label { font-family:system-ui,sans-serif; font-size:.7rem; text-transform:uppercase;
    letter-spacing:.12em; color:var(--dim); margin-top:22px; }
  .poem { font-style:italic; border-left:3px solid var(--accent); padding-left:16px; }
  .theme { color:var(--dim); font-size:.9rem; margin-top:24px; }
  h2 { font-size:1rem; letter-spacing:.06em; margin:48px 0 8px; font-family:system-ui,sans-serif;
    text-transform:uppercase; color:var(--dim); }
  ul { list-style:none; padding:0; } li { padding:9px 0; border-bottom:1px solid var(--line); }
  li a { font-weight:bold; }
  .dim { color:var(--dim); font-weight:normal; }
  .nav { font-family:system-ui,sans-serif; font-size:.85rem; margin-top:10px; }
  footer { margin-top:40px; color:var(--dim); font-size:.8rem; font-family:system-ui,sans-serif; }
"""


def _shell(title: str, body: str) -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{html.escape(title)}</title>\n<style>{_CSS}</style>\n</head>\n<body>\n"
        f"<div class=\"wrap\">\n{body}\n"
        "<footer>Made each morning by an always-on agent · Amazon Bedrock · Lambda · EventBridge</footer>\n"
        "</div>\n</body>\n</html>"
    )


def _card(row: dict) -> str:
    def esc(key):
        return html.escape(str(row.get(key, "")))

    word = html.escape(str(row.get("display_word", row.get("word", ""))))
    poem = html.escape(str(row.get("poem", ""))).replace("\n", "<br>")
    return (
        f'<div class="card">\n'
        f'  <h1 class="word">{word}</h1>\n'
        f'  <div class="pron">{esc("pronunciation")}</div>\n'
        f'  <div class="pos">{esc("part_of_speech")}</div>\n'
        f'  <p class="def">{esc("definition")}</p>\n'
        f'  <div class="label">Origin</div><div>{esc("etymology")}</div>\n'
        f'  <div class="label">In a sentence</div><div>&ldquo;{esc("example_sentence")}&rdquo;</div>\n'
        f'  <div class="label">Verse</div><p class="poem">{poem}</p>\n'
        f'  <div class="theme">{esc("theme_note")}</div>\n'
        f'</div>'
    )


def _archive_list(rows: list, prefix: str = "") -> str:
    items = "\n".join(
        f'<li><a href="{prefix}words/{_slug(r)}.html">'
        f'{html.escape(str(r.get("display_word", r.get("word", ""))))}</a>'
        f' <span class="dim">&mdash; {html.escape(str(r.get("definition", "")))}</span></li>'
        for r in rows
    )
    return f"<ul>{items}</ul>" if items else '<p class="dim">The archive begins today.</p>'


def _render_index(today: dict, archive: list) -> str:
    past = archive[1:41]
    body = (
        f'<div class="kicker">Daily Lexicon &middot; {html.escape(str(today.get("date", "")))}</div>\n'
        f'{_card(today)}\n'
        f'<h2>Recent words</h2>\n{_archive_list(past)}\n'
        f'<p class="nav"><a href="archive.html">See all past words &rarr;</a></p>'
    )
    return _shell("Daily Lexicon", body)


def _render_word_page(row: dict) -> str:
    body = (
        f'<div class="kicker">Daily Lexicon &middot; {html.escape(str(row.get("date", "")))}</div>\n'
        f'{_card(row)}\n'
        f'<p class="nav"><a href="../index.html">&larr; Today</a> &middot; '
        f'<a href="../archive.html">All words</a></p>'
    )
    return _shell(f'{row.get("display_word", row.get("word", ""))} · Daily Lexicon', body)


def _render_archive(archive: list) -> str:
    body = (
        f'<div class="kicker">Daily Lexicon</div>\n'
        f'<h2>Every word so far ({len(archive)})</h2>\n'
        f'{_archive_list(archive)}\n'
        f'<p class="nav"><a href="index.html">&larr; Back to today</a></p>'
    )
    return _shell("Archive · Daily Lexicon", body)
