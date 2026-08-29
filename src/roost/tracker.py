"""The port every app fills.

The agent's lifecycle is fixed: wake on a schedule, sense the world, reason over
memory, remember the result, publish a page, and alert you when it matters. A
Tracker is the one thing that changes between an app that teaches a word and one
that watches a flight price. app.py knows only this interface, never the concept.

To add an app: subclass Tracker, implement the six methods, register it in
adapters/__init__.py, and add a config-env to samconfig.toml. Nothing else moves.
"""

from abc import ABC, abstractmethod


class Tracker(ABC):
    # Identity. `slug` selects the adapter (ADAPTER env var) and names the app.
    slug: str = "tracker"
    title: str = "Tracker"

    @abstractmethod
    def collect(self) -> dict:
        """Sense the world right now: weather, a live price, whatever feeds it."""

    @abstractmethod
    def reason(self, ctx: dict, history: list) -> dict | None:
        """Turn context + memory into one record, or None to do nothing.

        The record MUST carry a string `id` (the item key; sortable so newest
        orders first) and a human `date`. Everything else is the app's own shape.
        For a once-a-day app, return the existing record when today is already
        done, so the run just refreshes the page instead of making a new one.
        """

    @abstractmethod
    def is_duplicate(self, record: dict, history: list) -> bool:
        """True if this record repeats one already stored (skip the save/email)."""

    @abstractmethod
    def is_noteworthy(self, record: dict, history: list) -> bool:
        """True if this record is worth an email. `history` is past records only."""

    @abstractmethod
    def email(self, record: dict, url: str) -> tuple[str, str]:
        """Return (subject, body) for the alert."""

    @abstractmethod
    def pages(self, record: dict, history: list) -> dict:
        """Return {relative_path: content}. Written to this app's own S3 bucket."""
