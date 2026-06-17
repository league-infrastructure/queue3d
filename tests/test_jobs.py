import struct

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.database import _ensure_print_job_labels
from app.dependencies import get_current_user, require_approved
from app.models import Location, PrintJob, User

# Minimal valid binary STL: 80-byte header + uint32(1) + one 50-byte triangle.
STL = b"\x00" * 80 + struct.pack("<I", 1) + struct.pack("<12fH", *([0.0] * 12), 0)


def _user(db, email):
    u = User(
        email=email,
        display_name=email.split("@")[0],
        provider="passphrase",
        provider_id=email,
        is_approved=True,
        is_admin=False,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _location(db):
    loc = Location(name="Lab A")
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


def _upload(client, loc):
    return client.post(
        "/api/upload",
        files={"file": ("thing.stl", STL, "application/octet-stream")},
        data={"location_id": str(loc.id)},
    )


def test_upload_assigns_sequential_label(client, db):
    loc = _location(db)
    u = _user(db, "stu@session.local")
    client.app.dependency_overrides[require_approved] = lambda: u
    try:
        r1 = _upload(client, loc)
        r2 = _upload(client, loc)
    finally:
        client.app.dependency_overrides.pop(require_approved, None)

    assert r1.status_code == 200 and r2.status_code == 200
    j1 = db.query(PrintJob).filter(PrintJob.id == r1.json()["id"]).one()
    j2 = db.query(PrintJob).filter(PrintJob.id == r2.json()["id"]).one()

    assert (j1.number, j2.number) == (1, 2)  # monotonic
    assert j1.name and j2.name  # a noun was assigned
    assert r1.json()["label"] == f"{j1.name} 1"
    assert " " in r1.json()["label"]  # "<noun> <number>"


def test_owner_can_download_others_cannot(client, db):
    loc = _location(db)
    owner = _user(db, "owner@session.local")
    client.app.dependency_overrides[require_approved] = lambda: owner
    try:
        job_id = _upload(client, loc).json()["id"]
    finally:
        client.app.dependency_overrides.pop(require_approved, None)

    # Owner may view/download their own file (for the STL viewer).
    client.app.dependency_overrides[get_current_user] = lambda: owner
    try:
        assert client.get(f"/api/jobs/{job_id}/download").status_code == 200
    finally:
        client.app.dependency_overrides.pop(get_current_user, None)

    # A different non-admin user may not.
    other = _user(db, "other@session.local")
    client.app.dependency_overrides[get_current_user] = lambda: other
    try:
        assert client.get(f"/api/jobs/{job_id}/download").status_code == 403
    finally:
        client.app.dependency_overrides.pop(get_current_user, None)


def test_upload_page_shows_jobs_with_viewer(client, db):
    loc = _location(db)
    u = _user(db, "stu@session.local")
    client.app.dependency_overrides[require_approved] = lambda: u
    try:
        _upload(client, loc)
    finally:
        client.app.dependency_overrides.pop(require_approved, None)

    client.app.dependency_overrides[get_current_user] = lambda: u
    try:
        r = client.get("/upload")
    finally:
        client.app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    body = r.text
    assert "My Print Jobs" in body  # merged section present
    assert "stl-canvas" in body  # viewer canvas for the job
    assert "/static/js/stl-viewer.js" in body  # viewer wired up


def test_my_jobs_redirects_to_upload(client, db):
    u = _user(db, "stu@session.local")
    client.app.dependency_overrides[get_current_user] = lambda: u
    try:
        r = client.get("/my-jobs", follow_redirects=False)
    finally:
        client.app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 302
    assert r.headers["location"].startswith("/upload")


def test_migration_adds_and_backfills_labels():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with eng.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE print_jobs "
                "(id VARCHAR PRIMARY KEY, created_at DATETIME, position INTEGER)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO print_jobs (id, created_at, position) "
                "VALUES ('a', '2026-01-01', 1), ('b', '2026-01-02', 2)"
            )
        )

    _ensure_print_job_labels(eng)

    with eng.begin() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(print_jobs)"))}
        assert {"number", "name"} <= cols
        rows = list(conn.execute(text("SELECT id, number, name FROM print_jobs ORDER BY number")))
    assert [r[1] for r in rows] == [1, 2]  # backfilled sequentially
    assert all(r[2] for r in rows)  # every row got a noun

    # Idempotent: a second run is a no-op and doesn't renumber.
    _ensure_print_job_labels(eng)
    with eng.begin() as conn:
        rows2 = list(conn.execute(text("SELECT number FROM print_jobs ORDER BY number")))
    assert [r[0] for r in rows2] == [1, 2]
