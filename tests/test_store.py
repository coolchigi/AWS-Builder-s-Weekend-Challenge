import store


def _packet():
    return {"date": "2026-08-22", "word": "Petrichor", "display_word": "Petrichor",
            "pronunciation": "/p/", "part_of_speech": "noun",
            "definition": "earthy rain scent", "etymology": "Greek",
            "example_sentence": "The petrichor rose.",
            "poem": "line one\nline two", "theme_note": "rainy day"}


def test_slug_is_url_safe():
    assert store._slug({"display_word": "Petrichor"}) == "petrichor"
    assert store._slug({"display_word": "Sui Generis"}) == "sui-generis"


def test_card_shows_word_and_poem():
    card = store._card(_packet())
    assert "Petrichor" in card
    assert "earthy rain scent" in card
    assert "line one<br>line two" in card


def test_card_escapes_user_content():
    packet = _packet()
    packet["definition"] = "<script>alert(1)</script>"
    card = store._card(packet)
    assert "<script>alert(1)</script>" not in card
    assert "&lt;script&gt;" in card


def test_index_links_archive_words():
    archive = [_packet(),
               {"display_word": "Halcyon", "word": "halcyon", "definition": "calm"}]
    html = store._render_index(_packet(), archive)
    assert 'href="words/halcyon.html"' in html
    assert 'href="archive.html"' in html


def test_word_page_has_back_links():
    html = store._render_word_page(_packet())
    assert 'href="../index.html"' in html
    assert 'href="../archive.html"' in html


def test_archive_page_lists_all():
    archive = [_packet(), {"display_word": "Halcyon", "word": "halcyon", "definition": "calm"}]
    html = store._render_archive(archive)
    assert "Every word so far (2)" in html
    assert 'href="words/petrichor.html"' in html
