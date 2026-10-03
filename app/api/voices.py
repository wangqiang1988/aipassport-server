from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from ..auth import get_device_or_user, require_device
from ..config import get_settings
from ..db import get_db
from ..models import Device, User, Voice

router = APIRouter(prefix="/api/v1/voices", tags=["voices"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serialize(v: Voice) -> dict:
    sender = v.sender
    return {
        "id": v.id,
        "sender": {
            "user_id": sender.id,
            "name": sender.name,
            "avatar_id": sender.avatar_id,
        },
        "duration_ms": v.duration_ms,
        "created_at": v.created_at.isoformat() + "Z" if v.created_at else None,
        "read_at": v.read_at.isoformat() + "Z" if v.read_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_voice(
    audio: UploadFile = File(...),
    recipient_id: int = Form(...),
    duration_ms: int = Form(...),
    device: Device = Depends(require_device),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    max_ms = settings.max_voice_duration_seconds * 1000
    if duration_ms <= 0 or duration_ms > max_ms:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "payload_too_large",
                "message": f"duration must be 1..{max_ms} ms",
            },
        )

    recipient = db.query(User).filter(User.id == recipient_id).first()
    if recipient is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "bad_request", "message": "recipient not found"},
        )

    data = await audio.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "bad_request", "message": "empty audio"},
        )

    voice = Voice(
        sender_user_id=device.owner_user_id,
        recipient_user_id=recipient.id,
        file_path="",
        duration_ms=duration_ms,
    )
    db.add(voice)
    db.flush()

    month = _utcnow().strftime("%Y-%m")
    rel_dir = Path(month)
    abs_dir = settings.voices_path / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    rel_path = rel_dir / f"{voice.id}.adpcm"
    abs_path = abs_dir / f"{voice.id}.adpcm"
    abs_path.write_bytes(data)
    voice.file_path = str(rel_path)
    db.commit()
    db.refresh(voice)
    return {
        "id": voice.id,
        "sender_id": voice.sender_user_id,
        "recipient_id": voice.recipient_user_id,
        "duration_ms": voice.duration_ms,
        "created_at": voice.created_at.isoformat() + "Z",
    }


@router.get("/inbox")
def inbox(
    limit: int = 50,
    before_id: int | None = None,
    device_user: tuple[Device | None, User | None] = Depends(get_device_or_user),
    db: Session = Depends(get_db),
) -> dict:
    device, user = device_user
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "no identity"},
        )
    q = db.query(Voice).filter(Voice.recipient_user_id == user.id)
    if before_id is not None:
        q = q.filter(Voice.id < before_id)
    rows = q.order_by(Voice.id.desc()).limit(min(limit, 200)).all()
    return {"voices": [_serialize(v) for v in rows]}


@router.get("/{voice_id}")
def download_voice(
    voice_id: int,
    device_user: tuple[Device | None, User | None] = Depends(get_device_or_user),
    db: Session = Depends(get_db),
):
    device, user = device_user
    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if voice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "voice not found"},
        )
    if user is None or (user.id != voice.sender_user_id and user.id != voice.recipient_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "not your voice"},
        )

    abs_path = Path(voice.file_path)
    if not abs_path.is_absolute():
        abs_path = get_settings().voices_path / voice.file_path

    if not abs_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "internal", "message": "voice file missing"},
        )
    data = abs_path.read_bytes()
    return Response(
        content=data,
        media_type="audio/adpcm",
        headers={
            "X-Voice-Duration-Ms": str(voice.duration_ms),
            "X-Voice-Codec": voice.codec,
            "X-Voice-Sample-Rate": str(voice.sample_rate),
            "X-Voice-Channels": str(voice.channels),
            "Content-Length": str(len(data)),
        },
    )


@router.post("/{voice_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    voice_id: int,
    device_user: tuple[Device | None, User | None] = Depends(get_device_or_user),
    db: Session = Depends(get_db),
) -> Response:
    device, user = device_user
    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if voice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "voice not found"},
        )
    if user is None or user.id != voice.recipient_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "not recipient"},
        )
    if voice.read_at is None:
        voice.read_at = _utcnow()
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{voice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voice(
    voice_id: int,
    device_user: tuple[Device | None, User | None] = Depends(get_device_or_user),
    db: Session = Depends(get_db),
) -> Response:
    device, user = device_user
    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if voice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "voice not found"},
        )
    if user is None or (user.id != voice.sender_user_id and user.id != voice.recipient_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "not allowed"},
        )

    settings_obj = get_settings()
    file_path = Path(voice.file_path)
    if not file_path.is_absolute():
        file_path = settings_obj.voices_path / voice.file_path
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass

    db.delete(voice)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
