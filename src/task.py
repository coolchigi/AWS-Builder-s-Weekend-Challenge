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


def collect() -> dict:
    """Sense the moment: date, weekday, season, time of day, and weather mood."""
    # Lambda runs in UTC; shift to Ottawa (UTC-4) so time of day is local.
    now = datetime.datetime.utcnow() - datetime.timedelta(hours=4)
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


def build_prompt(ctx: dict, used_words: list) -> str:
    used = ", ".join(used_words) if used_words else "(none yet)"
    return (
        f"Date: {ctx['date']} ({ctx['weekday']}, {ctx['season']}).\n"
        f"Time of day: {ctx['time_of_day']}.\n"
        f"Weather right now: {ctx['weather']}.\n"
        f"Words already taught (do NOT reuse): {used}.\n\n"
        "Choose today's word so its mood matches the weather and time of day, then "
        "return the JSON packet described in your instructions."
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
