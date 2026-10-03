from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    password_salt: Mapped[str] = mapped_column(String(32))
    avatar_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    short_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    device_token: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    paired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner_user: Mapped["User"] = relationship("User", lazy="joined")


class Pairing(Base):
    __tablename__ = "pairings"

    id: Mapped[int] = mapped_column(primary_key=True)
    pairing_code: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    pairing_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_uuid: Mapped[str] = mapped_column(String(36), index=True)
    confirmed_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    status: Mapped[int] = mapped_column(Integer, default=0)  # 0=pending 1=confirmed 2=expired
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Voice(Base):
    __tablename__ = "voices"

    id: Mapped[int] = mapped_column(primary_key=True)
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(256))
    duration_ms: Mapped[int] = mapped_column(Integer)
    sample_rate: Mapped[int] = mapped_column(Integer, default=16000)
    codec: Mapped[str] = mapped_column(String(16), default="ima-adpcm")
    channels: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_user_id], lazy="joined")
    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_user_id], lazy="joined")
