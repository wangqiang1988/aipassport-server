from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import new_token, require_user_web
from ..config import get_settings
from ..db import get_db
from ..models import Device, Pairing, User

router = APIRouter(prefix="/api/v1", tags=["pair"])


class PairStartIn(BaseModel):
    device_uuid: str = Field(min_length=8, max_length=64)


class PairConfirmIn(BaseModel):
    pairing_code: str = Field(min_length=4, max_length=10)


class UnpairIn(BaseModel):
    device_id: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _gen_pairing_code(db: Session, length: int) -> str:
    for _ in range(50):
        lo = 10 ** (length - 1)
        hi = 10**length
        code = f"{secrets.randbelow(hi - lo) + lo}"
        exists = db.query(Pairing).filter(Pairing.pairing_code == code).first()
        if exists is None:
            return code
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"code": "internal", "message": "could not generate unique code"},
    )


def _user_dict(u: User) -> dict:
    return {"id": u.id, "name": u.name, "avatar_id": u.avatar_id}


def _device_dict(d: Device) -> dict:
    return {
        "device_id": d.id,
        "device_token": d.device_token,
        "user": _user_dict(d.owner_user),
    }


def _find_pending_by_token(db: Session, token: str) -> Pairing | None:
    return db.query(Pairing).filter(Pairing.pairing_token == token).first()


@router.post("/pair/start")
def pair_start(body: PairStartIn, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    code = _gen_pairing_code(db, settings.pairing_code_length)
    pairing = Pairing(
        pairing_code=code,
        pairing_token=new_token(settings.token_bytes),
        device_uuid=body.device_uuid,
        status=0,
        expires_at=_utcnow() + timedelta(seconds=settings.pairing_code_ttl_seconds),
    )
    db.add(pairing)
    db.commit()
    db.refresh(pairing)
    return {
        "pairing_code": pairing.pairing_code,
        "pairing_token": pairing.pairing_token,
        "expires_at": pairing.expires_at.isoformat() + "Z",
    }


@router.post("/pair/confirm")
def pair_confirm(
    body: PairConfirmIn,
    user: User = Depends(require_user_web),
    db: Session = Depends(get_db),
) -> dict:
    pairing = db.query(Pairing).filter(Pairing.pairing_code == body.pairing_code).first()
    if pairing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "pairing code not found"},
        )
    if pairing.status == 2 or pairing.expires_at < _utcnow():
        if pairing.status != 2:
            pairing.status = 2
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "conflict", "message": "pairing code expired"},
        )
    if pairing.status == 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "conflict", "message": "pairing code already used"},
        )

    device = db.query(Device).filter(Device.device_uuid == pairing.device_uuid).first()
    settings = get_settings()
    token = new_token(settings.token_bytes)
    if device is None:
        device = Device(
            device_uuid=pairing.device_uuid,
            owner_user_id=user.id,
            short_code=pairing.pairing_code,
            device_token=token,
            paired_at=_utcnow(),
            last_seen=_utcnow(),
        )
        db.add(device)
    else:
        device.owner_user_id = user.id
        device.short_code = pairing.pairing_code
        device.device_token = token
        device.paired_at = _utcnow()
        device.last_seen = _utcnow()

    pairing.status = 1
    pairing.confirmed_user_id = user.id
    db.commit()
    db.refresh(device)
    return _device_dict(device)


@router.get("/pair/check")
def pair_check(
    device_uuid: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "missing pairing_token"},
        )
    pairing_token = authorization[7:].strip()
    pairing = _find_pending_by_token(db, pairing_token)
    if pairing is None or pairing.device_uuid != device_uuid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "invalid pairing_token"},
        )
    if pairing.status == 1:
        device = db.query(Device).filter(Device.device_uuid == pairing.device_uuid).first()
        if device is None or device.owner_user_id is None:
            return {"status": "pending"}
        return _device_dict(device)
    return {"status": "pending"}


@router.post("/devices/unpair", status_code=status.HTTP_204_NO_CONTENT)
def devices_unpair(body: UnpairIn, db: Session = Depends(get_db)) -> Response:
    settings = get_settings()
    device = db.query(Device).filter(Device.id == body.device_id).first()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "device not found"},
        )
    device.owner_user_id = None
    device.device_token = None
    device.paired_at = None
    device.short_code = None
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
