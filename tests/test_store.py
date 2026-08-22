import store


def _packet():
    return {"date": "2026-08-22", "word": "Petrichor", "pronunciation": "/p/",
            "part_of_speech": "noun", "definition": "earthy rain scent",
            "etymology": "Greek", "example_sentence": "The petrichor rose.",
            "poem": "line one\nline two", "theme_note": "rainy day"}


def test_render_html_shows_word_and_poem():
    html = store._render_html(_packet(), [_packet()])
    assert "Petrichor" in html
    assert "earthy rain scent" in html
    # poem newline becomes a <br>
    assert "line one<br>line two" in html


def test_render_html_escapes_user_content():
    packet = _packet()
    packet["definition"] = "<script>alert(1)</script>"
    html = store._render_html(packet, [packet])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_html_lists_archive_entries():
    archive = [_packet(),
               {"display_word": "Halcyon", "word": "halcyon", "definition": "calm"}]
    html = store._render_html(_packet(), archive)
    assert "Halcyon" in html


def test_render_html_handles_empty_archive():
    html = store._render_html(_packet(), [_packet()])
    assert "The archive begins today." in html
