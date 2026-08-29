"""Daily Lexicon: one uncommon, beautiful word a day, themed to the weather.

The first Roost app. It senses the day, asks Bedrock for a word whose mood fits,
remembers every word so it never repeats, publishes a page + browsable archive,
and emails you the word. Everything word-specific lives in this one file.
"""

import datetime
import html
import json
import os
import re

from roost import agent
from roost.tracker import Tracker

REQUIRED_KEYS = (
    "word", "pronunciation", "part_of_speech", "definition",
    "etymology", "example_sentence", "poem", "theme_note",
)

SYSTEM_PROMPT = (
    "You are Daily Lexicon, an always-on creative agent and lover of rare words. "
    "Each day you choose ONE uncommon, genuinely beautiful English word whose mood "
    "matches the moment: the weather and the time of day. A grey drizzly morning "
    "might call for something like 'gloaming' or 'petrichor'; a bright afternoon for "
    "'effervescent' or 'luminous'. Let the word feel like the day feels. You are "
    "given words you have already used; never reuse them, and drift into fresh "
    "territory over time. Reply ONLY as JSON with exactly these keys: {\"word\": "
    "string, \"pronunciation\": string, \"part_of_speech\": string, \"definition\": "
    "string, \"etymology\": string, \"example_sentence\": string, \"poem\": string "
    "(2-4 short lines that use the word and echo the mood, '\\n' between lines), "
    "\"theme_note\": string (one line on how it fits the weather and time of day)}. "
    "No commentary outside the JSON."
)


class WordTracker(Tracker):
    slug = "word"
    title = "Daily Lexicon"

    def collect(self) -> dict:
        # Lambda runs in UTC; shift to Ottawa (UTC-4) so time of day is local.
        now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)
        month = now.month
        season = {12: "winter", 1: "winter", 2: "winter",
                  3: "spring", 4: "spring", 5: "spring",
                  6: "summer", 7: "summer", 8: "summer",
                  9: "autumn", 10: "autumn", 11: "autumn"}[month]
        hour = now.hour
        time_of_day = ("night" if hour < 6 else "morning" if hour < 12
                       else "afternoon" if hour < 18 else "evening")
        return {
            "date": now.date().isoformat(),
            "weekday": now.strftime("%A"),
            "season": season,
            "time_of_day": time_of_day,
            "weather": _weather_mood(),
        }

    def reason(self, ctx: dict, history: list) -> dict | None:
        # Once a day: if today already has a word, reuse it (just refresh pages).
        today = next((r for r in history if r.get("date") == ctx["date"]), None)
        if today:
            return dict(today)

        used = [str(r.get("display_word", r.get("word", ""))) for r in history]
        packet = agent.generate(
            model_id=os.environ["MODEL_ID"],
            system_prompt=SYSTEM_PROMPT,
            user_prompt=_build_prompt(ctx, used),
            required_keys=REQUIRED_KEYS,
            max_tokens=900,
            temperature=0.8,
        )
        word = str(packet["word"]).strip()
        packet["display_word"] = word
        packet["word"] = word.lower()
        packet["date"] = ctx["date"]
        packet["id"] = ctx["date"]  # one record per day
        return packet

    def is_duplicate(self, record: dict, history: list) -> bool:
        return any(r.get("date") == record.get("date") for r in history)

    def is_noteworthy(self, record: dict, history: list) -> bool:
        return True  # every new word is worth sending

    def email(self, record: dict, url: str) -> tuple[str, str]:
        subject = f"Today's word: {record.get('display_word', record.get('word', ''))}"
        return subject, _render_email(record, url)

    def pages(self, record: dict, history: list) -> dict:
        out = {
            "today.json": json.dumps(record, ensure_ascii=False, default=str),
            "index.html": _render_index(record, history),
            "archive.html": _render_archive(history),
        }
        seen = set()
        for row in history:
            slug = _slug(row)
            if slug not in seen:
                seen.add(slug)
                out[f"words/{slug}.html"] = _render_word_page(row)
        return out


def _build_prompt(ctx: dict, used_words: list) -> str:
    used = ", ".join(w for w in used_words if w) or "(none yet)"
    return (
        f"Date: {ctx['date']} ({ctx['weekday']}, {ctx['season']}).\n"
        f"Time of day: {ctx['time_of_day']}.\n"
        f"Weather right now: {ctx['weather']}.\n"
        f"Words already taught (do NOT reuse): {used}.\n\n"
        "Choose today's word so its mood matches the weather and time of day, then "
        "return the JSON packet described in your instructions."
    )


def _render_email(record: dict, url: str) -> str:
    return (
        f"{record.get('display_word', record.get('word', ''))}  {record.get('pronunciation', '')}\n"
        f"{record.get('part_of_speech', '')}\n\n"
        f"{record.get('definition', '')}\n\n"
        f"Origin: {record.get('etymology', '')}\n\n"
        f"\"{record.get('example_sentence', '')}\"\n\n"
        f"{record.get('poem', '')}\n\n"
        f"— {record.get('theme_note', '')}\n\n"
        f"See it, and the archive: {url}\n"
    )


def _weather_mood() -> str:
    """Best-effort weather via Open-Meteo (no key). Falls back gracefully."""
    import urllib.request

    lat_lon = os.environ.get("WEATHER_LATLON", "45.42,-75.70")
    try:
        lat, lon = lat_lon.split(",")
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat.strip()}&longitude={lon.strip()}&current=weather_code,temperature_2m"
        )
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        code = data["current"]["weather_code"]
        temp = data["current"]["temperature_2m"]
        warmth = "cold" if temp < 8 else "mild" if temp < 22 else "warm"
        return f"{warmth} and {_sky(code)}"
    except Exception:
        return "unknown"


def _sky(code: int) -> str:
    if code == 0:
        return "clear"
    if code in (1, 2, 3):
        return "cloudy"
    if code in (45, 48):
        return "foggy"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rainy"
    if 71 <= code <= 77 or 85 <= code <= 86:
        return "snowy"
    if code >= 95:
        return "stormy"
    return "changeable"


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


def _slug(row: dict) -> str:
    word = str(row.get("display_word", row.get("word", ""))).lower()
    return re.sub(r"[^a-z0-9]+", "-", word).strip("-") or "word"


def _shell(title: str, body: str) -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{html.escape(title)}</title>\n<style>{_CSS}</style>\n</head>\n<body>\n"
        f"<div class=\"wrap\">\n{body}\n"
        "<footer>Made each morning by an always-on agent · Amazon Bedrock · Lambda · EventBridge · Roost</footer>\n"
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


def _render_index(today: dict, history: list) -> str:
    past = [r for r in history if r.get("date") != today.get("date")][:40]
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


def _render_archive(history: list) -> str:
    body = (
        f'<div class="kicker">Daily Lexicon</div>\n'
        f'<h2>Every word so far ({len(history)})</h2>\n'
        f'{_archive_list(history)}\n'
        f'<p class="nav"><a href="index.html">&larr; Back to today</a></p>'
    )
    return _shell("Archive · Daily Lexicon", body)
