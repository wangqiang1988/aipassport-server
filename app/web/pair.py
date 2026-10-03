from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..auth import require_user_web
from ..db import get_db
from ..models import Pairing, User
from ..templating import templates

router = APIRouter(tags=["web-pair"])


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(url=path, status_code=status.HTTP_303_SEE_OTHER)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/pair", response_class=HTMLResponse)
def pair_form(request: Request, user: User = Depends(require_user_web)):
    return templates.TemplateResponse(request, "pair.html", {"error": None, "code": ""})


@router.post("/pair")
def pair_submit(
    request: Request,
    code: str = Form(...),
    user: User = Depends(require_user_web),
    db: Session = Depends(get_db),
):
    code = code.strip()
    pairing = db.query(Pairing).filter(Pairing.pairing_code == code).first()
    if pairing is None:
        return templates.TemplateResponse(
            request,
            "pair.html",
            {"error": "找不到这个短码", "code": code},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if pairing.status == 2 or pairing.expires_at < _utcnow():
        if pairing.status != 2:
            pairing.status = 2
            db.commit()
        return templates.TemplateResponse(
            request,
            "pair.html",
            {"error": "短码已过期，请让设备重新生成", "code": code},
            status_code=status.HTTP_409_CONFLICT,
        )
    if pairing.status == 1:
        if pairing.confirmed_user_id == user.id:
            return _redirect("/home")
        return templates.TemplateResponse(
            request,
            "pair.html",
            {"error": "这个短码已经被别人用了", "code": code},
            status_code=status.HTTP_409_CONFLICT,
        )

    from ..api.pair import _device_dict
    from ..auth import new_token
    from ..config import get_settings
    from ..models import Device

    settings = get_settings()
    device = db.query(Device).filter(Device.device_uuid == pairing.device_uuid).first()
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
    return _redirect("/home")
