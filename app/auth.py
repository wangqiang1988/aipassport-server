from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Device, User

SESSION_COOKIE = "session"
WEB_SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    digest = _digest(password, salt)
    return salt, digest


def verify_password(password: str, salt: str, expected: str) -> bool:
    return hmac.compare_digest(_digest(password, salt), expected)


def _digest(password: str, salt: str) -> str:
    h = hashlib.sha256()
    h.update(salt.encode("utf-8"))
    h.update(password.encode("utf-8"))
    return h.hexdigest()


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def _signer() -> TimestampSigner:
    return TimestampSigner(get_settings().secret_key, salt="bppassport-web-session")


def issue_web_session(user_id: int) -> str:
    return _signer().sign(str(user_id)).decode("ascii")


def read_web_session(token: str) -> int | None:
    try:
        value = _signer().unsign(token, max_age=WEB_SESSION_MAX_AGE)
        return int(value.decode("ascii"))
    except (BadSignature, SignatureExpired, ValueError):
        return None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "unauthorized", "message": "missing or invalid credentials"},
    )


def get_device_or_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> tuple[Device | None, User | None]:
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        device = db.query(Device).filter(Device.device_token == token).first()
        if device is None:
            raise _unauthorized()
        if device.owner_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "forbidden", "message": "device not paired"},
            )
        user = db.query(User).filter(User.id == device.owner_user_id).first()
        return device, user

    session = request.cookies.get(SESSION_COOKIE)
    if session:
        uid = read_web_session(session)
        if uid is not None:
            user = db.query(User).filter(User.id == uid).first()
            if user is not None:
                return None, user

    raise _unauthorized()


def require_device(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Device:
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized()
    token = authorization[7:].strip()
    device = db.query(Device).filter(Device.device_token == token).first()
    if device is None or device.owner_user_id is None:
        raise _unauthorized()
    device.last_seen = datetime.now(timezone.utc)
    db.commit()
    return device


def require_user_web(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise _unauthorized()
    uid = read_web_session(token)
    if uid is None:
        raise _unauthorized()
    user = db.query(User).filter(User.id == uid).first()
    if user is None:
        raise _unauthorized()
    return user


def require_user_web_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    uid = read_web_session(token)
    if uid is None:
        return None
    return db.query(User).filter(User.id == uid).first()
