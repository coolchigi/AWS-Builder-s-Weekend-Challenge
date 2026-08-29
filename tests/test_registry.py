import pytest

from adapters import load
from adapters.flight import FlightTracker
from adapters.word import WordTracker


def test_load_known_adapters():
    assert isinstance(load("word"), WordTracker)
    assert isinstance(load("flight"), FlightTracker)


def test_load_unknown_raises():
    with pytest.raises(KeyError):
        load("nope")
