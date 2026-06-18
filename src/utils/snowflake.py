"""简易雪花 ID（字符串），用于 chunk_id / kb_id。"""
from __future__ import annotations

import threading
import time

_EPOCH_MS = 1_704_067_200_000  # 2024-01-01 UTC
_lock = threading.Lock()
_last_ms = 0
_seq = 0


def next_snowflake_id() -> str:
    global _last_ms, _seq
    with _lock:
        now_ms = int(time.time() * 1000)
        if now_ms == _last_ms:
            _seq = (_seq + 1) & 0xFFF
            if _seq == 0:
                while now_ms <= _last_ms:
                    time.sleep(0.001)
                    now_ms = int(time.time() * 1000)
        else:
            _seq = 0
        _last_ms = now_ms
        value = ((now_ms - _EPOCH_MS) << 12) | _seq
        return str(value)
