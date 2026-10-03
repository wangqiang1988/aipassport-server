from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import contacts as api_contacts
from .api import me as api_me
from .api import pair as api_pair
from .api import users as api_users
from .api import voices as api_voices
from .config import get_settings
from .db import init_db
from .web import home as web_home
from .web import login as web_login
from .web import pair as web_pair
from .web import send as web_send


settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())
log = logging.getLogger("bppassport")


_BASE_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _BASE_DIR / "static"


def _error_payload(detail) -> tuple[int, dict]:
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return detail.get("status", 500), {"error": {"code": detail["code"], "message": detail["message"]}}
    if isinstance(detail, dict):
        return 500, {"error": {"code": "internal", "message": str(detail)}}
    return 500, {"error": {"code": "internal", "message": str(detail)}}


def create_app() -> FastAPI:
    settings.voices_path.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="bppassport",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    app.include_router(api_users.router)
    app.include_router(api_me.router)
    app.include_router(api_contacts.router)
    app.include_router(api_pair.router)
    app.include_router(api_voices.router)

    app.include_router(web_login.router)
    app.include_router(web_home.router)
    app.include_router(web_pair.router)
    app.include_router(web_send.router)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict:
        return {"ok": True}

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": {"code": exc.detail["code"], "message": exc.detail["message"]}},
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": str(exc.detail)}},
        )

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        log.info("bppassport ready: voices_dir=%s db=%s", settings.voices_path, settings.database_url)

    return app


app = create_app()
