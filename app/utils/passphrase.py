"""Session passphrase generation, normalization, and time helpers.

The admin's main screen displays a short, memorable three-word passphrase
(adjective-noun-noun, e.g. "excitable-flower-hat") that students type to sign
in. Words come from the ``wonderwords`` library.
"""

import re
from datetime import datetime, timedelta, timezone

from wonderwords import RandomWord

# How long a generated passphrase remains usable for new logins.
PASSPHRASE_TTL = timedelta(hours=1)

_rw = RandomWord()
_WORD_KW = {"word_min_length": 3, "word_max_length": 8}


def generate_passphrase() -> str:
    """Return a memorable three-word passphrase like 'excitable-flower-hat'."""
    adjective = _rw.word(include_parts_of_speech=["adjectives"], **_WORD_KW)
    noun1 = _rw.word(include_parts_of_speech=["nouns"], **_WORD_KW)
    noun2 = _rw.word(include_parts_of_speech=["nouns"], **_WORD_KW)
    return "-".join(w.lower() for w in (adjective, noun1, noun2))


def normalize(value: str) -> str:
    """Normalize a passphrase for comparison.

    Lowercase, strip, and collapse any run of whitespace / dashes / underscores
    into single dashes so a student typing "Excitable Flower Hat" or
    "excitable_flower_hat" matches the stored "excitable-flower-hat".
    """
    value = re.sub(r"[\s_-]+", "-", value.strip().lower())
    return value.strip("-")


def ensure_utc(dt: datetime) -> datetime:
    """Treat a possibly-naive datetime as UTC.

    SQLite drops tzinfo, so datetimes read back from the DB are naive even
    though they were stored as UTC. This makes comparisons and ISO output safe.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
