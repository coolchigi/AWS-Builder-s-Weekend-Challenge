import task


def test_build_prompt_includes_context_and_memory():
    ctx = {"date": "2026-08-22", "weekday": "Saturday",
           "season": "summer", "weather": "warm and rainy"}
    prompt = task.build_prompt(ctx, ["halcyon", "susurrus"])
    assert "2026-08-22" in prompt
    assert "warm and rainy" in prompt
    assert "halcyon" in prompt and "susurrus" in prompt


def test_build_prompt_handles_empty_memory():
    ctx = {"date": "2026-08-22", "weekday": "Saturday",
           "season": "summer", "weather": "clear"}
    assert "(none yet)" in task.build_prompt(ctx, [])


def test_render_email_contains_word_and_link():
    packet = {"word": "Petrichor", "pronunciation": "/p/", "part_of_speech": "noun",
              "definition": "d", "etymology": "e", "example_sentence": "s",
              "poem": "line1\nline2", "theme_note": "t"}
    email = task.render_email(packet, "http://example.com")
    assert "Petrichor" in email
    assert "http://example.com" in email


def test_collect_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(task, "_weather_mood", lambda: "cold and snowy")
    ctx = task.collect()
    assert set(ctx) == {"date", "weekday", "season", "weather"}
    assert ctx["season"] in {"winter", "spring", "summer", "autumn"}
    assert ctx["weather"] == "cold and snowy"


def test_sky_mapping():
    assert task._sky(0) == "clear"
    assert task._sky(2) == "cloudy"
    assert task._sky(61) == "rainy"
    assert task._sky(73) == "snowy"
    assert task._sky(95) == "stormy"
