from datetime import timedelta

from app.models import SessionPassphrase, User, _utcnow
from app.utils.passphrase import generate_passphrase, normalize


def _make_passphrase(db, phrase="alpha-beta-gamma", *, minutes=60, active=True):
    sp = SessionPassphrase(
        phrase=phrase,
        expires_at=_utcnow() + timedelta(minutes=minutes),
        is_active=active,
    )
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return sp


# --- generator / normalize ---

def test_generate_passphrase_uses_known_lowercase_words():
    from app.utils.passphrase import _ADJECTIVES, _NOUNS

    vocab = set(_ADJECTIVES) | set(_NOUNS)
    # Sample many times to cover the random shapes/words.
    for _ in range(50):
        phrase = generate_passphrase()
        parts = phrase.split("-")
        assert 2 <= len(parts) <= 3
        assert phrase == phrase.lower()
        assert all(p in vocab for p in parts)
        assert len(parts) == len(set(parts))  # no repeated word within a phrase


def test_normalize_collapses_separators_and_case():
    assert normalize("  Excitable Flower Hat ") == "excitable-flower-hat"
    assert normalize("excitable_flower_hat") == "excitable-flower-hat"
    assert normalize("excitable--flower--hat") == "excitable-flower-hat"


# --- login flow ---

def test_login_with_valid_passphrase_creates_approved_user(client, db):
    _make_passphrase(db, "alpha-beta-gamma")
    resp = client.post(
        "/auth/login/passphrase",
        data={"name": "Maya", "passphrase": "Alpha Beta Gamma"},  # different casing/spaces
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"

    user = db.query(User).filter(User.provider == "passphrase").one()
    assert user.display_name == "Maya"
    assert user.is_approved is True
    assert user.is_admin is False


def test_login_requires_a_name(client, db):
    _make_passphrase(db, "alpha-beta-gamma")
    resp = client.post(
        "/auth/login/passphrase",
        data={"name": "  ", "passphrase": "alpha-beta-gamma"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error" in resp.headers["location"]
    assert db.query(User).filter(User.provider == "passphrase").count() == 0


def test_login_with_invalid_passphrase_rejected(client, db):
    _make_passphrase(db, "alpha-beta-gamma")
    resp = client.post(
        "/auth/login/passphrase",
        data={"name": "Maya", "passphrase": "wrong-words-here"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error" in resp.headers["location"]
    assert db.query(User).filter(User.provider == "passphrase").count() == 0


def test_login_with_expired_passphrase_rejected(client, db):
    _make_passphrase(db, "alpha-beta-gamma", minutes=-1)  # already expired
    resp = client.post(
        "/auth/login/passphrase",
        data={"name": "Maya", "passphrase": "alpha-beta-gamma"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error" in resp.headers["location"]
    assert db.query(User).filter(User.provider == "passphrase").count() == 0


def test_session_survives_passphrase_expiry(client, db):
    sp = _make_passphrase(db, "alpha-beta-gamma")
    client.post(
        "/auth/login/passphrase",
        data={"name": "Maya", "passphrase": "alpha-beta-gamma"},
    )
    assert client.get("/api/me").json()["is_approved"] is True

    # Passphrase expires — existing session must NOT be logged out.
    sp.expires_at = _utcnow() - timedelta(minutes=1)
    db.commit()

    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["is_approved"] is True


# --- admin refresh ---

def test_refresh_replaces_active_passphrase_and_invalidates_old(client, db):
    from app.dependencies import require_admin

    old = _make_passphrase(db, "old-pass-phrase")
    admin = User(
        email="teacher@jointheleague.org",
        display_name="Teacher",
        provider="google",
        provider_id="x",
        is_admin=True,
        is_approved=True,
    )
    db.add(admin)
    db.commit()

    client.app.dependency_overrides[require_admin] = lambda: admin
    try:
        resp = client.post("/api/admin/session/passphrase/refresh")
    finally:
        client.app.dependency_overrides.pop(require_admin, None)

    assert resp.status_code == 200
    new_phrase = resp.json()["phrase"]
    assert 2 <= len(new_phrase.split("-")) <= 3
    assert new_phrase != "old-pass-phrase"

    db.refresh(old)
    assert old.is_active is False
    actives = db.query(SessionPassphrase).filter(SessionPassphrase.is_active == True).all()
    assert len(actives) == 1
    assert actives[0].phrase == new_phrase

    # The old phrase can no longer be used for a new login.
    resp2 = client.post(
        "/auth/login/passphrase",
        data={"name": "Bob", "passphrase": "old-pass-phrase"},
        follow_redirects=False,
    )
    assert "error" in resp2.headers["location"]
