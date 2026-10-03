from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_device
from ..db import get_db
from ..models import Device

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me")
def me(device: Device = Depends(require_device), db: Session = Depends(get_db)) -> dict:
    user = device.owner_user
    short_code = device.short_code or ""
    paired_at = device.paired_at.isoformat() + "Z" if device.paired_at else None
    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "avatar_id": user.avatar_id,
            "created_at": user.created_at.isoformat() + "Z",
        },
        "device": {
            "id": device.id,
            "short_code": short_code,
            "paired_at": paired_at,
        },
    }
