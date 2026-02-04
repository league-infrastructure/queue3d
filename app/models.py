import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MODEL_COLORS = ["#7ec8e3", "#b39ddb", "#fff176", "#ffb74d", "#81c784", "#e57373"]


def _random_color() -> str:
    return random.choice(MODEL_COLORS)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_id: Mapped[str] = mapped_column(String, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    jobs: Mapped[list["PrintJob"]] = relationship(back_populates="user")


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    jobs: Mapped[list["PrintJob"]] = relationship(back_populates="location")


class PrintJob(Base):
    __tablename__ = "print_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String, nullable=False, default=_random_color)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="jobs")
    location: Mapped["Location"] = relationship(back_populates="jobs")

    VALID_STATUSES = {"queued", "printing", "printed", "failed", "not_printable", "rejected"}
    ACTIVE_STATUSES = {"queued", "printing"}
    COMPLETED_STATUSES = {"printed", "not_printable", "rejected"}
