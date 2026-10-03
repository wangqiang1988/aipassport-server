from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..auth import require_user_web
from ..db import get_db
from ..models import User
from ..templating import templates

router = APIRouter(tags=["web-send"])


@router.get("/send", response_class=HTMLResponse)
def send_page(
    request: Request,
    to: int | None = None,
    user: User = Depends(require_user_web),
    db: Session = Depends(get_db),
):
    contacts = (
        db.query(User).filter(User.id != user.id).order_by(User.id.asc()).all()
    )
    recipient = None
    if to is not None:
        recipient = db.query(User).filter(User.id == to).first()
    return templates.TemplateResponse(
        request,
        "send.html",
        {"contacts": contacts, "to": recipient},
    )
