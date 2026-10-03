from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from ..auth import (
    SESSION_COOKIE,
    WEB_SESSION_MAX_AGE,
    hash_password,
    issue_web_session,
    verify_password,
)
from ..db import get_db
from ..models import User
from fastapi import Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    avatar_id: int | None = None


class LoginIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "avatar_id": user.avatar_id,
        "created_at": user.created_at.isoformat() + "Z" if user.created_at else None,
    }


def _set_session_cookie(response: Response, user_id: int) -> None:
    token = issue_web_session(user_id)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=WEB_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)) -> dict:
    if db.query(User).filter(User.name == body.name).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "conflict", "message": "name already taken"},
        )
    salt, digest = hash_password(body.password)
    user = User(
        name=body.name,
        password_hash=digest,
        password_salt=salt,
        avatar_id=body.avatar_id if body.avatar_id is not None else (hash(body.name) % 12) + 1,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "conflict", "message": "name already taken"},
        )
    db.refresh(user)
    _set_session_cookie(response, user.id)
    return {"user": _user_dict(user)}


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.name == body.name).first()
    if user is None or not verify_password(body.password, user.password_salt, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "invalid name or password"},
        )
    _set_session_cookie(response, user.id)
    return {"user": _user_dict(user)}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp
