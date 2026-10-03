from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..auth import (
    SESSION_COOKIE,
    WEB_SESSION_MAX_AGE,
    hash_password,
    issue_web_session,
    require_user_web_optional,
    verify_password,
)
from ..db import get_db
from ..models import User
from ..templating import templates

router = APIRouter(tags=["web-auth"])


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(url=path, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, user: User | None = Depends(require_user_web_optional)):
    if user is not None:
        return _redirect("/home")
    return templates.TemplateResponse(request, "login.html", {"error": None, "name": ""})


@router.post("/login")
def login_submit(
    request: Request,
    name: str = Form(...),
    password: str = Form(...),
    action: str = Form("login"),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.name == name).first()

    if action == "register":
        if user is not None:
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "这个名字已经被用了", "name": name},
                status_code=status.HTTP_409_CONFLICT,
            )
        salt, digest = hash_password(password)
        user = User(
            name=name,
            password_hash=digest,
            password_salt=salt,
            avatar_id=(hash(name) % 12) + 1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if user is None or not verify_password(password, user.password_salt, user.password_hash):
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "账号或密码不对", "name": name},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

    token = issue_web_session(user.id)
    resp = _redirect("/home")
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=WEB_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp


@router.get("/logout")
def logout_get():
    resp = _redirect("/login")
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp
