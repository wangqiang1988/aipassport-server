from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..auth import require_user_web, require_user_web_optional
from ..db import get_db
from ..models import User, Voice
from ..templating import templates

router = APIRouter(tags=["web-home"])


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(url=path, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/")
def root(user: User | None = Depends(require_user_web_optional)):
    return _redirect("/home" if user else "/login")


@router.get("/home", response_class=HTMLResponse)
def home(
    request: Request,
    user: User = Depends(require_user_web),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Voice)
        .filter(Voice.recipient_user_id == user.id)
        .order_by(Voice.id.desc())
        .limit(50)
        .all()
    )
    voices = [
        {
            "id": v.id,
            "sender_name": v.sender.name,
            "sender_avatar": v.sender.avatar_id,
            "duration_ms": v.duration_ms,
            "created_at": v.created_at,
            "read_at": v.read_at,
        }
        for v in rows
    ]
    contacts = (
        db.query(User)
        .filter(User.id != user.id)
        .order_by(User.id.asc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "user": user,
            "voices": voices,
            "contacts": contacts,
        },
    )


@router.post("/voices/{voice_id}/read")
def mark_read_web(
    voice_id: int,
    user: User = Depends(require_user_web),
    db: Session = Depends(get_db),
):
    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if voice is not None and voice.recipient_user_id == user.id and voice.read_at is None:
        from datetime import datetime, timezone

        voice.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    return _redirect("/home")


@router.post("/voices/{voice_id}/delete")
def delete_voice_web(
    voice_id: int,
    user: User = Depends(require_user_web),
    db: Session = Depends(get_db),
):
    from pathlib import Path

    from ..config import get_settings

    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if voice is not None and (
        voice.sender_user_id == user.id or voice.recipient_user_id == user.id
    ):
        settings = get_settings()
        path = Path(voice.file_path)
        if not path.is_absolute():
            path = settings.voices_path / voice.file_path
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        db.delete(voice)
        db.commit()
    return _redirect("/home")
