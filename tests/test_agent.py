import pytest

from roost import agent

KEYS = ("word", "poem")


def test_parse_plain_json():
    assert agent._parse_json('{"word": "halcyon"}') == {"word": "halcyon"}


def test_parse_json_in_code_fence():
    text = 'Here you go:\n```json\n{"word": "susurrus"}\n```'
    assert agent._parse_json(text)["word"] == "susurrus"


def test_parse_json_embedded_in_prose():
    text = 'Today: {"word": "petrichor", "n": 1} — enjoy!'
    assert agent._parse_json(text)["word"] == "petrichor"


def test_parse_json_rejects_garbage():
    with pytest.raises(ValueError):
        agent._parse_json("no json here at all")


def test_validate_accepts_complete_packet():
    agent._validate({"word": "x", "poem": "y"}, KEYS)  # no raise


def test_validate_rejects_missing_key():
    with pytest.raises(ValueError):
        agent._validate({"word": "x"}, KEYS)


def test_validate_rejects_blank_value():
    with pytest.raises(ValueError):
        agent._validate({"word": "x", "poem": "   "}, KEYS)
