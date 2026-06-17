# coding=utf-8
# !/usr/bin/python
# -*- coding:utf-8 -*-
# @author  : 刘立军
# @time    : 2024-12-23
# @Description: 处理token。
# @version : V0.5

'''
# 安装 PyJWT，在 Python 中生成和校验 JWT 令牌
pip install pyjwt
'''
import base64
import math
import os
import random

# 下面代码可以防止引用同级目录模块时出现错误：找不到模块
import sys
from pathlib import Path

from fontTools.misc.eexec import encrypt,decrypt

from src.settings import get_settings

separator = "\u2016"

_settings = get_settings()
SECRET_KEY = _settings.jwt_secret_key

# 对JWT编码解码的算法。JWT不加密，任何人都能用它恢复原始信息。
ALGORITHM = "HS256"

# DEFAULT_TOKEN_EXPIRE_MINUTES = config['token']["default_expires_time"]
DEFAULT_TOKEN_EXPIRE_MINUTES = _settings.token_default_expires_time

R = 8437138593

# 加密签名：userid + timestamp
def get_sign(encrypted_text,access_token_expires):
    t = str(math.floor(access_token_expires.timestamp()))
    #print(f"access_token_expires is {t}")
    src_text = encrypted_text + separator + t
    cipherstring, _ = encrypt(src_text.encode('utf-8'), 8437138593)  # 确保传入的是字节类型
    # 将字节数据转换为Base64编码的字符串
    encoded_cipherstring = base64.b64encode(cipherstring).decode('utf-8')
    return encoded_cipherstring


from datetime import datetime, timedelta, timezone
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError


# 生成JWT
def create_access_token(data: dict, encrypted_text: str = None, expire_minutes: int | None = None):
    to_encode = data.copy()
    if expire_minutes is not None and expire_minutes > 0:
        expires_delta = timedelta(minutes=expire_minutes)
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=DEFAULT_TOKEN_EXPIRE_MINUTES)
    if encrypted_text is not None and encrypted_text != "":  # 加密签名
        sign = get_sign(encrypted_text, expire)
        to_encode["sign"] = sign  # 直接将字节串添加到字典中
    to_encode["exp"] = int(expire.timestamp())

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# 解析并校验JWT。
def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError as exc:
        raise ExpiredSignatureError("登录已过期，请重新登录") from exc
    except InvalidTokenError as exc:
        raise InvalidTokenError("无效的登录凭证") from exc

    sub: str = payload.get("sub")
    if not sub:
        raise InvalidTokenError("Token 缺少用户信息")
    sign: str = payload.get("sign")
    if not sign:
        raise InvalidTokenError("Token 缺少签名")
    exp: int = payload.get("exp")
    if not exp:
        raise InvalidTokenError("Token 缺少过期时间")

    now = math.floor(datetime.now(timezone.utc).timestamp())
    if now > exp:
        raise ExpiredSignatureError("登录已过期，请重新登录")

    try:
        decrypted_data = base64.b64decode(sign)
        plain_sign, _ = decrypt(decrypted_data, R)
        plain_sign = plain_sign.decode("utf-8")
    except Exception as exc:
        raise InvalidTokenError("Token 签名校验失败") from exc

    arr = plain_sign.split(separator)
    if len(arr) != 2:
        raise InvalidTokenError("Token 签名格式错误")
    userid, timestamp_str = arr[0], arr[1]
    try:
        timestamp = int(timestamp_str)
    except ValueError as exc:
        raise InvalidTokenError("Token 签名时间戳无效") from exc
    if timestamp != exp:
        raise InvalidTokenError("Token 签名与过期时间不一致")
    return userid


if __name__ == '__main__':
    # data = {"sub": "wang"}
    # encrypted_text = "56008507@qq.com"
    # expire_minutes = 15
    # token = create_access_token(data,encrypted_text,expire_minutes)
    # print(token)
    #
    userid = decode_access_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ3eHkiLCJzaWduIjoidFdDYVFiaHF4eXcyWEw5a1VhcktvUT09IiwiZXhwIjoxNzQxNDMxNDA2fQ.gHMZhp_igxpCu8btZV0oaq2XDa276Q-6cJKPvC8bZ58")
    #
    print(userid)