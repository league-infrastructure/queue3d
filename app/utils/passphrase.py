"""Session passphrase generation, normalization, and time helpers.

The admin's main screen displays a short, memorable passphrase
(e.g. "goofy-pickle-barge") that students type to sign in. Words are drawn
from curated, kid-friendly lists in ``app/data/`` — replace those files to
change the vocabulary; no code change needed.
"""

import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

# How long a generated passphrase remains usable for new logins.
PASSPHRASE_TTL = timedelta(hours=1)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Phrase shapes the generator may produce. Each tuple is a sequence of slots,
# every slot drawing from the adjective or noun list. A shape is chosen at
# random per passphrase. Trim this to a single tuple to force one shape.
PATTERNS = (
    ("adjective", "noun"),
    ("adjective", "noun", "noun"),
    ("adjective", "adjective", "noun"),
)


def _load_words(filename: str) -> list[str]:
    """Read a word list: one lowercase word per line; '#'/blank lines ignored."""
    path = _DATA_DIR / filename
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        word = line.strip().lower()
        if word and not word.startswith("#"):
            words.append(word)
    return words


_ADJECTIVES = _load_words("adjectives.txt")
_NOUNS = _load_words("nouns.txt")
_WORDS = {"adjective": _ADJECTIVES, "noun": _NOUNS}


def generate_passphrase() -> str:
    """Return a memorable dash-joined passphrase, e.g. 'goofy-pickle-barge'.

    Picks a random shape from PATTERNS and fills each slot from the matching
    word list, never repeating a word within a single phrase.
    """
    pattern = random.choice(PATTERNS)
    words: list[str] = []
    for slot in pattern:
        choices = [w for w in _WORDS[slot] if w not in words]
        words.append(random.choice(choices))
    return "-".join(words)


def random_noun() -> str:
    """Return a single random noun, used for per-job labels like 'house 53'."""
    return random.choice(_NOUNS)


def normalize(value: str) -> str:
    """Normalize a passphrase for comparison.

    Lowercase, strip, and collapse any run of whitespace / dashes / underscores
    into single dashes so a student typing "Goofy Pickle Barge" or
    "goofy_pickle_barge" matches the stored "goofy-pickle-barge".
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
