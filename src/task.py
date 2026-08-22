"""THE CREATIVE BRAIN. Re-skin this file to change what the agent makes.

Daily Lexicon: each day the agent conjures one uncommon, beautiful English word,
themed to the date and weather, and writes a tiny original poem that uses it.
It is told which words it has already taught so it never repeats and can drift
toward new territory over time.

To adapt to a different creative prompt you usually only touch:
    collect()       -> the context the agent creates from
    SYSTEM_PROMPT   -> what it makes and the JSON shape it returns
    build_prompt()  -> how context + memory reach the model
    render_email()  -> how the result reads in your inbox
"""

import datetime
import json
import os
import urllib.request

SYSTEM_PROMPT = (
    "You are Daily Lexicon, an always-on creative agent and lover of rare words. "
    "Each day you choose ONE uncommon, genuinely beautiful English word and "
    "present it with care, subtly themed to the given date and weather. You are "
    "given words you have already used; never reuse them, and let your choices "
    "drift into fresh territory over time. Reply ONLY as JSON with exactly these "
    "keys: {\"word\": string, \"pronunciation\": string, \"part_of_speech\": "
    "string, \"definition\": string, \"etymology\": string, \"example_sentence\": "
    "string, \"poem\": string (2-4 short lines that use the word and echo the "
    "day's mood, '\\n' between lines), \"theme_note\": string (one line on how it "
    "fits today)}. No commentary outside the JSON."
)


def collect() -> dict:
    """Sense the day: date, weekday, season, and a one-word weather mood."""
    today = datetime.date.today()
    month = today.month
    season = {12: "winter", 1: "winter", 2: "winter",
              3: "spring", 4: "spring", 5: "spring",
              6: "summer", 7: "summer", 8: "summer",
              9: "autumn", 10: "autumn", 11: "autumn"}[month]
    return {
        "date": today.isoformat(),
        "weekday": today.strftime("%A"),
        "season": season,
        "weather": _weather_mood(),
    }


def build_prompt(ctx: dict, used_words: list) -> str:
    used = ", ".join(used_words) if used_words else "(none yet)"
    return (
        f"Date: {ctx['date']} ({ctx['weekday']}, {ctx['season']}).\n"
        f"Weather mood today: {ctx['weather']}.\n"
        f"Words already taught (do NOT reuse): {used}.\n\n"
        "Choose today's word and return the JSON packet described in your "
        "instructions."
    )


def render_email(packet: dict, site_url: str) -> str:
    return (
        f"{packet['word']}  {packet.get('pronunciation', '')}\n"
        f"{packet.get('part_of_speech', '')}\n\n"
        f"{packet.get('definition', '')}\n\n"
        f"Origin: {packet.get('etymology', '')}\n\n"
        f"\"{packet.get('example_sentence', '')}\"\n\n"
        f"{packet.get('poem', '')}\n\n"
        f"— {packet.get('theme_note', '')}\n\n"
        f"See it, and the archive: {site_url}\n"
    )


def _weather_mood() -> str:
    """Best-effort weather via Open-Meteo (no key). Falls back gracefully."""
    lat_lon = os.environ.get("WEATHER_LATLON", "40.71,-74.01")
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
        sky = _sky(code)
        warmth = "cold" if temp < 8 else "mild" if temp < 22 else "warm"
        return f"{warmth} and {sky}"
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
