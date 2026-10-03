from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_device
from ..db import get_db
from ..models import Device, User

router = APIRouter(prefix="/api/v1", tags=["contacts"])


@router.get("/contacts")
def contacts(device: Device = Depends(require_device), db: Session = Depends(get_db)) -> dict:
    users = db.query(User).order_by(User.id.asc()).all()
    items = [
        {"user_id": u.id, "name": u.name, "avatar_id": u.avatar_id}
        for u in users
    ]
    return {"contacts": items}
