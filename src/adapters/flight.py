"""Flight Watch: track one route's fare and ping you when it's worth booking.

The second Roost app, and proof the platform holds: a completely different job
(watch a live price, alert only on a real drop) reusing the same core. It reads
the cheapest fare from a live source, remembers every observation, asks Bedrock
for a one-line verdict, and emails you only on a new low or a meaningful drop.

The fare source is pluggable. Today it uses Duffel, with the token supplied as the
DUFFEL_TOKEN env var on the function; when no token is set it falls back to a mock
fare feed so the app is always demoable. Losing a provider costs one function, not
the app (Amadeus closed its free tier mid-build; the swap was a single file).
"""

import datetime
import json
import os
import random
import urllib.request

from roost import agent
from roost.tracker import Tracker

_VERDICT_SYSTEM = (
    "You are Flight Watch, a terse travel-fare assistant. Given a route and its "
    "recent prices, reply ONLY as JSON with keys {\"headline\": string (<= 8 words), "
    "\"advice\": string (one sentence, book-now vs wait, plain and honest)}. "
    "No commentary outside the JSON."
)


class FlightTracker(Tracker):
    slug = "flight"
    title = "Flight Watch"

    def __init__(self):
        route = os.environ.get("ROUTE", "YOW-LOS")
        parts = route.split("-", 1)
        if len(parts) != 2 or not all(p.strip() for p in parts):
            raise ValueError(f"ROUTE must be 'ORIGIN-DESTINATION' (e.g. YOW-LOS), got: {route!r}")
        self.origin, self.destination = parts[0].strip().upper(), parts[1].strip().upper()
        self.depart_date = os.environ.get("DEPART_DATE", "2026-12-15")
        self.return_date = os.environ.get("RETURN_DATE", "")  # "" = one-way
        self.adults = os.environ.get("ADULTS", "1")
        self.currency = os.environ.get("CURRENCY", "CAD")
        self.cabin = os.environ.get("CABIN_CLASS", "economy")
        self.drop_pct = float(os.environ.get("FLIGHT_DROP_PCT", "5"))

    # --- lifecycle ---------------------------------------------------------

    def collect(self) -> dict:
        live = _duffel_cheapest(
            self.origin, self.destination, self.depart_date,
            self.return_date, self.adults, self.currency, self.cabin,
        )
        return live or _mock_fare(self.origin, self.destination, self.currency)

    def reason(self, ctx: dict, history: list) -> dict:
        now = datetime.datetime.now(datetime.timezone.utc)
        prices = _past_prices(history)
        prev_min = min(prices) if prices else None
        prev_recent = prices[0] if prices else None
        price = float(ctx["price"])

        record = {
            "id": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": now.date().isoformat(),
            "route": f"{self.origin}-{self.destination}",
            "origin": self.origin,
            "destination": self.destination,
            "depart_date": self.depart_date,
            "return_date": self.return_date,
            "price": price,
            "currency": ctx.get("currency", self.currency),
            "carrier": ctx.get("carrier", ""),
            "stops": ctx.get("stops"),
            "source": ctx.get("source", "mock"),
            "prev_min": prev_min,
            "is_new_low": prev_min is None or price < prev_min,
        }
        record["headline"], record["advice"] = _verdict(record, prev_min, prev_recent)
        return record

    def is_duplicate(self, record: dict, history: list) -> bool:
        # Skip a redundant save when the newest stored observation is the same
        # price on the same day; the site still refreshes.
        if not history:
            return False
        last = history[0]
        return (str(last.get("date")) == record["date"]
                and _num(last.get("price")) == record["price"])

    def is_noteworthy(self, record: dict, history: list) -> bool:
        prices = _past_prices(history)
        if not prices:
            return True  # first observation: send the baseline
        price = record["price"]
        prev_min = min(prices)
        recent = prices[0]
        drop_pct = (recent - price) / recent * 100 if recent else 0
        return price < prev_min or drop_pct >= self.drop_pct

    def email(self, record: dict, url: str) -> tuple[str, str]:
        money = _money(record["price"], record["currency"])
        flag = "  ↓ NEW LOW" if record.get("is_new_low") else ""
        subject = f"{record['route']} fare: {money}{flag}"
        body = (
            f"{record['headline']}\n\n"
            f"{record['origin']} → {record['destination']}"
            f"  ({record['depart_date']}{' / ' + record['return_date'] if record['return_date'] else ', one-way'})\n"
            f"Cheapest now: {money}"
            f"{'  (' + record['carrier'] + ')' if record.get('carrier') else ''}\n"
        )
        if record.get("prev_min") is not None:
            body += f"Previous low seen: {_money(record['prev_min'], record['currency'])}\n"
        body += f"\n{record['advice']}\n\nPrice history: {url}\n"
        if record.get("source") == "mock":
            body += "\n(mock fare feed, set the DUFFEL_TOKEN env var on the function for live prices)\n"
        return subject, body

    def pages(self, record: dict, history: list) -> dict:
        return {
            "prices.json": json.dumps(_json_feed(history), ensure_ascii=False, default=str),
            "index.html": _render_page(record, history),
        }


# --- Duffel (live fares) ---------------------------------------------------

def _duffel_token():
    """Duffel token from the DUFFEL_TOKEN env var, or None to use the mock feed.

    Set it on the Lambda (Console -> Configuration -> Environment variables) so
    the secret lives only on the function, never in the template, CLI, or repo.
    """
    return os.environ.get("DUFFEL_TOKEN") or None


def _duffel_cheapest(origin, destination, depart, ret, adults, currency, cabin):
    """Cheapest offer from Duffel, or None (no token / no offers / error).

    One POST to /air/offer_requests?return_offers=true returns priced offers
    inline; we pick the lowest total_amount. A round trip adds a return slice.
    """
    token = _duffel_token()
    if not token:
        return None

    slices = [{"origin": origin, "destination": destination, "departure_date": depart}]
    if ret:
        slices.append({"origin": destination, "destination": origin, "departure_date": ret})
    try:
        count = max(1, int(adults))
    except (TypeError, ValueError):
        count = 1
    payload = {"data": {
        "slices": slices,
        "passengers": [{"type": "adult"} for _ in range(count)],
        "cabin_class": cabin or "economy",
    }}

    try:
        data = _duffel_post(
            "https://api.duffel.com/air/offer_requests?return_offers=true",
            token, payload,
        )
        offers = (data.get("data") or {}).get("offers") or []
        if not offers:
            return None
        best = min(offers, key=lambda o: float(o["total_amount"]))
        owner = best.get("owner") or {}
        segments = ((best.get("slices") or [{}])[0].get("segments")) or []
        return {
            "price": float(best["total_amount"]),
            "currency": best.get("total_currency", currency),
            "carrier": owner.get("iata_code") or owner.get("name", ""),
            "stops": max(0, len(segments) - 1),
            "source": "duffel",
        }
    except Exception:
        return None


def _duffel_post(url: str, token: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Duffel-Version": os.environ.get("DUFFEL_VERSION", "v2"),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read())


def _mock_fare(origin, destination, currency) -> dict:
    """Deterministic-per-hour fake fare, so demos vary and sometimes dip to a low.

    Base fare is read from the MOCK_BASE env var (set per-stack in samconfig.toml).
    Falls back to a route-aware default when MOCK_BASE is not set:
      YOW-LOS  ~1400 CAD  (Ottawa → Lagos, typically 1–2 stops via Europe or MidEast)
      YOW-ABV  ~1600 CAD  (Ottawa → Abuja, slightly less served, tends to run higher)
      anything else: 1200 CAD
    """
    _ROUTE_DEFAULTS = {
        ("YOW", "LOS"): 1400,
        ("YOW", "ABV"): 1600,
    }
    default_base = _ROUTE_DEFAULTS.get((origin, destination), 1200)
    base = float(os.environ.get("MOCK_BASE", str(default_base)))
    seed = int(datetime.datetime.now(datetime.timezone.utc).timestamp()) // 3600
    rng = random.Random(f"{origin}{destination}{seed}")
    return {
        "price": round(base + rng.randint(-190, 240), 2),
        "currency": currency,
        "carrier": rng.choice(["AC", "BA", "KL", "LH", "TK"]),
        "stops": rng.choice([1, 1, 2]),
        "source": "mock",
    }


# --- verdict (Bedrock, best-effort) ---------------------------------------

def _verdict(record, prev_min, prev_recent):
    model = os.environ.get("MODEL_ID")
    if model and os.environ.get("FLIGHT_USE_BEDROCK", "true").lower() != "false":
        try:
            prompt = (
                f"Route {record['route']}, depart {record['depart_date']}"
                f"{', return ' + record['return_date'] if record['return_date'] else ', one-way'}.\n"
                f"Cheapest right now: {_money(record['price'], record['currency'])}.\n"
                f"Lowest seen before: {_money(prev_min, record['currency']) if prev_min is not None else 'none yet'}.\n"
                f"Previous check: {_money(prev_recent, record['currency']) if prev_recent is not None else 'none yet'}.\n"
                "Give the verdict."
            )
            packet = agent.generate(
                model_id=model, system_prompt=_VERDICT_SYSTEM, user_prompt=prompt,
                required_keys=("headline", "advice"), max_tokens=180, temperature=0.4,
            )
            return str(packet["headline"]).strip(), str(packet["advice"]).strip()
        except Exception:
            pass
    return _fallback_verdict(record, prev_min, prev_recent)


def _fallback_verdict(record, prev_min, prev_recent):
    price = record["price"]
    if prev_min is None:
        return "Baseline set", "First reading for this route. We'll watch it from here."
    if price < prev_min:
        return "New low!", "Cheapest we've seen. If the dates work, this is a strong time to book."
    if prev_recent and price < prev_recent:
        return "Dipping", "Down since the last check, but not a record. Worth a look."
    if prev_recent and price > prev_recent:
        return "Ticking up", "Higher than last check. Holding off looks reasonable."
    return "Holding steady", "No real movement. Nothing to do yet."


# --- helpers ---------------------------------------------------------------

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _past_prices(history: list) -> list:
    """Past prices, newest first (history is already sorted newest-first)."""
    return [p for p in (_num(r.get("price")) for r in history) if p is not None]


def _money(value, currency) -> str:
    return f"{currency} {float(value):,.0f}"


def _json_feed(history: list) -> list:
    return [{"id": r.get("id"), "date": r.get("date"),
             "price": _num(r.get("price")), "currency": r.get("currency")}
            for r in history]


# --- rendering (a small departures-board page) -----------------------------

_CSS = """
  :root { --bg:#0f1826; --ink:#eaf1fb; --dim:#8fa2bd; --card:#16233a; --line:#26374f;
    --up:#e0654e; --down:#43c08a; --accent:#5aa9ff; }
  @media (prefers-color-scheme: light) {
    :root { --bg:#eef3fa; --ink:#132133; --dim:#5b6b83; --card:#ffffff; --line:#d5e0ee;
      --up:#c0432c; --down:#1f9d68; --accent:#1667d6; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
    font-family:'IBM Plex Mono',ui-monospace,'SF Mono',Menlo,monospace; line-height:1.55; }
  a { color:var(--accent); text-decoration:none; } a:hover { text-decoration:underline; }
  .wrap { max-width:640px; margin:0 auto; padding:44px 22px 72px; }
  .kicker { text-transform:uppercase; letter-spacing:.22em; font-size:.7rem; color:var(--dim); }
  .route { font-size:2.2rem; font-weight:600; margin:.15em 0 0; letter-spacing:.04em; }
  .when { color:var(--dim); font-size:.85rem; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:14px;
    padding:26px 28px; margin-top:18px; }
  .price { font-size:3rem; font-weight:600; letter-spacing:.02em; }
  .badge { display:inline-block; font-size:.72rem; letter-spacing:.12em; text-transform:uppercase;
    padding:4px 10px; border-radius:999px; margin-left:10px; vertical-align:middle; }
  .badge.low { background:var(--down); color:#04120c; }
  .badge.hold { background:var(--line); color:var(--dim); }
  .headline { font-size:1.15rem; margin:14px 0 4px; }
  .advice { color:var(--dim); }
  .meta { color:var(--dim); font-size:.85rem; margin-top:16px; }
  h2 { font-size:.78rem; letter-spacing:.14em; text-transform:uppercase; color:var(--dim);
    margin:36px 0 10px; }
  table { width:100%; border-collapse:collapse; font-size:.85rem; }
  td { padding:7px 0; border-bottom:1px solid var(--line); }
  td.p { text-align:right; font-variant-numeric:tabular-nums; }
  .spark { margin-top:10px; }
  footer { margin-top:38px; color:var(--dim); font-size:.78rem; }
"""


def _spark(prices: list) -> str:
    """A tiny inline SVG line of the last ~24 prices, oldest -> newest."""
    pts = list(reversed(prices[:24]))
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1
    w, h = 600, 60
    step = w / (len(pts) - 1)
    coords = " ".join(
        f"{i * step:.1f},{h - (p - lo) / span * (h - 8) - 4:.1f}" for i, p in enumerate(pts)
    )
    last_x = (len(pts) - 1) * step
    last_y = h - (pts[-1] - lo) / span * (h - 8) - 4
    return (
        f'<svg class="spark" viewBox="0 0 {w} {h}" width="100%" height="60" '
        f'preserveAspectRatio="none" role="img" aria-label="Recent price trend">'
        f'<polyline points="{coords}" fill="none" stroke="var(--accent)" stroke-width="2"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3.5" fill="var(--accent)"/>'
        f'</svg>'
    )


def _render_page(record: dict, history: list) -> str:
    import html

    money = _money(record["price"], record["currency"])
    low = record.get("is_new_low")
    badge = ('<span class="badge low">new low</span>' if low
             else '<span class="badge hold">watching</span>')
    prices = _past_prices(history)

    rows = "\n".join(
        f'<tr><td>{html.escape(str(r.get("id", "")).replace("T", " ").rstrip("Z"))}</td>'
        f'<td class="p">{_money(_num(r.get("price")) or 0, r.get("currency", record["currency"]))}</td></tr>'
        for r in history[:20]
    )
    dates = (f'{record["depart_date"]} / {record["return_date"]}'
             if record["return_date"] else f'{record["depart_date"]} · one-way')
    source = "live via Duffel" if record.get("source") == "duffel" else "mock fare feed"

    body = (
        f'<div class="kicker">Flight Watch &middot; {html.escape(dates)}</div>\n'
        f'<div class="route">{html.escape(record["origin"])} &rarr; {html.escape(record["destination"])}</div>\n'
        f'<div class="when">updated {html.escape(str(record.get("id", "")).replace("T", " ").rstrip("Z"))} UTC · {source}</div>\n'
        f'<div class="card">\n'
        f'  <div><span class="price">{money}</span>{badge}</div>\n'
        f'  <div class="headline">{html.escape(str(record.get("headline", "")))}</div>\n'
        f'  <div class="advice">{html.escape(str(record.get("advice", "")))}</div>\n'
        f'  <div class="meta">'
        f'{"carrier " + html.escape(record["carrier"]) + " · " if record.get("carrier") else ""}'
        f'{("nonstop" if record.get("stops") == 0 else str(record.get("stops")) + " stop(s)") if record.get("stops") is not None else ""}'
        f'{" · previous low " + _money(record["prev_min"], record["currency"]) if record.get("prev_min") is not None else ""}'
        f'</div>\n'
        f'  {_spark(prices)}\n'
        f'</div>\n'
        f'<h2>Recent readings ({len(history)})</h2>\n'
        f'<table>{rows}</table>'
    )
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">\n"
        "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap\">\n"
        f"<title>{html.escape(record['origin'])} → {html.escape(record['destination'])} · Flight Watch</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n<div class=\"wrap\">\n{body}\n"
        f"<footer>{html.escape(record['origin'])} &rarr; {html.escape(record['destination'])} · watched by an always-on agent · Duffel · Amazon Bedrock · Lambda · EventBridge · Roost</footer>\n"
        "</div>\n</body>\n</html>"
    )
