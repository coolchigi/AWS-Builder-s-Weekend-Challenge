import adapters.flight as flight
from adapters.flight import FlightTracker


def _rec(price, date="2026-08-22", ts=None):
    return {"id": ts or f"{date}T00:00:00Z", "date": date, "price": price, "currency": "CAD"}


def test_first_observation_is_noteworthy():
    assert FlightTracker().is_noteworthy(_rec(1300), []) is True


def test_new_all_time_low_is_noteworthy():
    hist = [_rec(1200), _rec(1250), _rec(1400)]
    assert FlightTracker().is_noteworthy(_rec(1150), hist) is True


def test_higher_price_not_noteworthy():
    hist = [_rec(1200), _rec(1250)]
    assert FlightTracker().is_noteworthy(_rec(1260), hist) is False


def test_meaningful_drop_is_noteworthy(monkeypatch):
    monkeypatch.setenv("FLIGHT_DROP_PCT", "5")
    t = FlightTracker()
    # newest past is 1000; a 6% drop to 940 fires even if 900 was seen before
    hist = [_rec(1000), _rec(900)]
    assert t.is_noteworthy(_rec(940), hist) is True
    assert t.is_noteworthy(_rec(980), hist) is False  # only 2% down


def test_is_duplicate_same_price_same_day():
    t = FlightTracker()
    hist = [_rec(1200, "2026-08-22")]
    assert t.is_duplicate(_rec(1200, "2026-08-22"), hist) is True
    assert t.is_duplicate(_rec(1201, "2026-08-22"), hist) is False
    assert t.is_duplicate(_rec(1200, "2026-08-23"), hist) is False


def test_mock_fare_shape():
    fare = flight._mock_fare("YOW", "LOS", "CAD")
    assert fare["source"] == "mock" and fare["currency"] == "CAD"
    assert isinstance(fare["price"], float) and fare["price"] > 0


def test_fallback_verdict_new_low():
    head, advice = flight._fallback_verdict(_rec(900), prev_min=1000, prev_recent=1050)
    assert "low" in head.lower() and advice


def test_reason_uses_fallback_without_model(monkeypatch):
    monkeypatch.delenv("MODEL_ID", raising=False)
    t = FlightTracker()
    ctx = {"price": 1180.0, "currency": "CAD", "carrier": "AC", "stops": 1, "source": "mock"}
    rec = t.reason(ctx, [_rec(1250), _rec(1300)])
    assert rec["price"] == 1180.0
    assert rec["is_new_low"] is True  # below prev_min 1250
    assert rec["headline"] and rec["advice"]
    assert rec["id"].endswith("Z") and rec["route"] == "YOW-LOS"


def test_page_renders_price_and_history():
    rec = {"id": "2026-08-22T12:00:00Z", "date": "2026-08-22", "route": "YOW-LOS",
           "origin": "YOW", "destination": "LOS", "depart_date": "2026-12-15",
           "return_date": "2026-12-29", "price": 1180.0, "currency": "CAD",
           "carrier": "AC", "stops": 1, "source": "mock", "prev_min": 1250.0,
           "is_new_low": True, "headline": "New low!", "advice": "Book it."}
    hist = [rec, _rec(1250), _rec(1300)]
    html = flight._render_page(rec, hist)
    assert "YOW" in html and "LOS" in html
    assert "CAD 1,180" in html and "new low" in html
    assert "<svg" in html  # sparkline present with >= 2 points


def test_spark_needs_two_points():
    assert flight._spark([1200]) == ""
    assert "<svg" in flight._spark([1200, 1250, 1180])
