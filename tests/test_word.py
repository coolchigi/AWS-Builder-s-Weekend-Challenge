import adapters.word as word
from adapters.word import WordTracker


def _packet(date="2026-08-22", w="Petrichor"):
    return {"id": date, "date": date, "word": w.lower(), "display_word": w,
            "pronunciation": "/p/", "part_of_speech": "noun",
            "definition": "earthy rain scent", "etymology": "Greek",
            "example_sentence": "The petrichor rose.",
            "poem": "line one\nline two", "theme_note": "rainy day"}


def test_build_prompt_includes_context_and_memory():
    ctx = {"date": "2026-08-22", "weekday": "Saturday", "season": "summer",
           "time_of_day": "morning", "weather": "warm and rainy"}
    prompt = word._build_prompt(ctx, ["halcyon", "susurrus"])
    assert "2026-08-22" in prompt and "warm and rainy" in prompt
    assert "morning" in prompt and "halcyon" in prompt and "susurrus" in prompt


def test_build_prompt_handles_empty_memory():
    ctx = {"date": "2026-08-22", "weekday": "Saturday", "season": "summer",
           "time_of_day": "morning", "weather": "clear"}
    assert "(none yet)" in word._build_prompt(ctx, [])


def test_slug_is_url_safe():
    assert word._slug({"display_word": "Petrichor"}) == "petrichor"
    assert word._slug({"display_word": "Sui Generis"}) == "sui-generis"


def test_card_escapes_user_content():
    p = _packet()
    p["definition"] = "<script>alert(1)</script>"
    card = word._card(p)
    assert "<script>alert(1)</script>" not in card and "&lt;script&gt;" in card


def test_index_links_and_excludes_today():
    today = _packet("2026-08-22", "Halcyon")
    history = [today, _packet("2026-08-21", "Petrichor")]
    html = word._render_index(today, history)
    assert 'href="words/petrichor.html"' in html
    assert 'href="archive.html"' in html
    # today should not appear in the "recent" list, only in the hero card
    assert html.count("petrichor.html") == 1


def test_reason_reuses_todays_record_without_calling_bedrock(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("Bedrock should not be called when today exists")
    monkeypatch.setattr(word.agent, "generate", boom)
    today = _packet("2026-08-22", "Halcyon")
    got = WordTracker().reason({"date": "2026-08-22"}, [today])
    assert got["display_word"] == "Halcyon"


def test_reason_generates_and_stamps_ids(monkeypatch):
    monkeypatch.setenv("MODEL_ID", "amazon.nova-lite-v1:0")
    monkeypatch.setattr(word.agent, "generate", lambda **k: {
        "word": "Gloaming", "pronunciation": "x", "part_of_speech": "noun",
        "definition": "d", "etymology": "e", "example_sentence": "s",
        "poem": "p", "theme_note": "t"})
    ctx = {"date": "2026-08-23", "weekday": "Sun", "season": "summer",
           "time_of_day": "evening", "weather": "cool and clear"}
    rec = WordTracker().reason(ctx, [])
    assert rec["id"] == "2026-08-23" and rec["date"] == "2026-08-23"
    assert rec["display_word"] == "Gloaming" and rec["word"] == "gloaming"


def test_is_duplicate_by_date():
    t = WordTracker()
    assert t.is_duplicate(_packet("2026-08-22"), [_packet("2026-08-22")]) is True
    assert t.is_duplicate(_packet("2026-08-23"), [_packet("2026-08-22")]) is False


def test_collect_shape(monkeypatch):
    monkeypatch.setattr(word, "_weather_mood", lambda: "cold and snowy")
    ctx = WordTracker().collect()
    assert set(ctx) == {"date", "weekday", "season", "time_of_day", "weather"}
    assert ctx["weather"] == "cold and snowy"
