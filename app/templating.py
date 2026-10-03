from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

_BASE_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def fmt_dt(value) -> str:
    if value is None:
        return ""
    try:
        return value.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


def fmt_duration(ms: int) -> str:
    if not ms:
        return "0s"
    s = ms // 1000
    m, s = divmod(s, 60)
    return f"{m}:{s:02d}" if m else f"{s}s"


def fmt_relative(value) -> str:
    if value is None:
        return ""
    now = __import__("datetime").datetime.utcnow()
    delta = now - value
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前"
    if seconds < 86400:
        return f"{seconds // 3600} 小时前"
    if seconds < 86400 * 30:
        return f"{seconds // 86400} 天前"
    return value.strftime("%Y-%m-%d")


templates.env.filters["fmt_dt"] = fmt_dt
templates.env.filters["fmt_duration"] = fmt_duration
templates.env.filters["fmt_relative"] = fmt_relative
