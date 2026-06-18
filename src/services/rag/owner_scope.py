"""用户 ID 与 Milvus INT64 owner_user_id 标量映射。"""
from __future__ import annotations

import zlib


def milvus_owner_user_id(user_id: int | str | None) -> int:
    """将业务 user_id（可能为非数字字符串）映射为 Milvus INT64 标量。"""
    if user_id is None or user_id == "" or user_id == "0" or user_id == 0:
        return 0
    if isinstance(user_id, int):
        return user_id
    text = str(user_id).strip()
    if text.isdigit():
        return int(text)
    return zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF
