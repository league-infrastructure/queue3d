from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base
from app.utils.passphrase import random_noun

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _ensure_print_job_labels(bind) -> None:
    """Additive migration: add number/name columns to print_jobs and backfill.

    The project has no migration tooling and create_all won't alter an existing
    table, so add the label columns in place and give any pre-existing rows a
    number + noun. Idempotent and safe on a fresh DB (columns already present,
    no rows to backfill).
    """
    with bind.begin() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(print_jobs)"))}
        if not cols:
            return
        if "number" not in cols:
            conn.execute(text("ALTER TABLE print_jobs ADD COLUMN number INTEGER"))
        if "name" not in cols:
            conn.execute(text("ALTER TABLE print_jobs ADD COLUMN name VARCHAR"))
        rows = list(
            conn.execute(
                text(
                    "SELECT id FROM print_jobs WHERE number IS NULL "
                    "ORDER BY created_at, position"
                )
            )
        )
        if not rows:
            return
        n = conn.execute(text("SELECT COALESCE(MAX(number), 0) FROM print_jobs")).scalar() or 0
        for (job_id,) in rows:
            n += 1
            conn.execute(
                text("UPDATE print_jobs SET number = :n, name = :nm WHERE id = :id"),
                {"n": n, "nm": random_noun(), "id": job_id},
            )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_print_job_labels(engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
