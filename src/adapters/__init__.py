"""The apps. Each module defines one Tracker; this registry maps slug -> class.

Adding an app = drop a module here, add its class to _CLASSES, deploy a stack
with ADAPTER=<slug>.
"""

from adapters.flight import FlightTracker
from adapters.word import WordTracker

_CLASSES = [WordTracker, FlightTracker]


def load(slug: str):
    for cls in _CLASSES:
        if cls.slug == slug:
            return cls()
    known = ", ".join(c.slug for c in _CLASSES)
    raise KeyError(f"unknown adapter '{slug}'. known: {known}")
