"""将数据库中的 UTC naive 时间格式化为本地展示时间。"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# 与定时调度 Asia/Shanghai 保持一致
DISPLAY_TZ = ZoneInfo("Asia/Shanghai")


def utc_naive_to_local(dt: datetime | None, tz: ZoneInfo = DISPLAY_TZ) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(tz)


def format_display_datetime(
    dt: datetime | None,
    fmt: str = "%Y-%m-%d %H:%M:%S",
    tz: ZoneInfo = DISPLAY_TZ,
) -> str:
    local = utc_naive_to_local(dt, tz)
    if local is None:
        return ""
    return local.strftime(fmt)
