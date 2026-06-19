import bcrypt


def _to_bytes(value: str | bytes) -> bytes:
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码是否与 bcrypt 哈希匹配。"""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(_to_bytes(plain_password), _to_bytes(hashed_password))
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """生成 bcrypt 哈希，与历史 passlib 写入的 $2b$ 格式兼容。"""
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt()).decode("utf-8")
