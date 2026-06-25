"""当前日期时间原生 Tool。"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def get_current_datetime(timezone: str = "Asia/Shanghai") -> dict:
    tz_name = (timezone or "Asia/Shanghai").strip() or "Asia/Shanghai"
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return {"ok": False, "error": f"未知时区: {tz_name}"}

    now = datetime.now(tz)
    return {
        "ok": True,
        "timezone": tz_name,
        "iso": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": _WEEKDAYS[now.weekday()],
        "formatted": now.strftime("%Y年%m月%d日 %H:%M:%S"),
    }
