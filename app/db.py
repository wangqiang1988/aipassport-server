from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base

_settings = get_settings()

_path = _settings.database_url.replace("sqlite:///", "")
if _path.startswith("./"):
    _abs = Path(_path).resolve()
    _abs.parent.mkdir(parents=True, exist_ok=True)
    _resolved_url = f"sqlite:///{_abs}"
else:
    _resolved_url = _settings.database_url

engine = create_engine(
    _resolved_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if _resolved_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    settings = get_settings()
    settings.voices_path.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _seed_if_empty()


def _seed_if_empty() -> None:
    from .auth import hash_password
    from .models import User

    with SessionLocal() as db:
        if db.query(User).count() > 0:
            return
        for name in ("爸爸", "妈妈"):
            salt, digest = hash_password("x")
            user = User(
                name=name,
                password_hash=digest,
                password_salt=salt,
                avatar_id=(hash(name) % 12) + 1,
            )
            db.add(user)
        db.commit()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "init":
        init_db()
        print("DB initialized + seed inserted (if empty).")
    elif cmd == "reset":
        if Path("data.sqlite").exists():
            Path("data.sqlite").unlink()
        init_db()
        print("DB reset.")
    else:
        print("usage: python -m app.db {init|reset}")
        sys.exit(2)
