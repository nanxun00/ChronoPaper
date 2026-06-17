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

    print("to_encode:",to_encode)

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# 解析并校验JWT。
def decode_access_token(token: str):

    print(token)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        print(payload)

        # 校验JWT完整性
        sub: str = payload.get("sub")
        if sub is None or sub == "":
            raise InvalidTokenError
        sign: str = payload.get("sign")
        if sign is None or sign == "":
            raise InvalidTokenError
        exp: int = payload.get("exp")
        if exp is None or exp == 0:
            raise InvalidTokenError

        print("exp:",exp)

        # 判断JWT是否过期
        now = math.floor(datetime.now(timezone.utc).timestamp())
        if now > exp:
            raise ExpiredSignatureError

        # 校验加密的签名
        decrypted_data = base64.b64decode(sign)
        # 解密字节数据
        plain_sign, _ = decrypt(decrypted_data, R)  # 解密元组
        plain_sign = plain_sign.decode('utf-8')

        print(plain_sign)

        if plain_sign is None:
            raise InvalidTokenError
        arr = plain_sign.split("‖")

        print(arr)


        if len(arr) != 2:
            raise InvalidTokenError
        userid = arr[0]
        print("userid:",userid)
        timestamp = int(arr[1])
        print("timestamp:",timestamp)
        if timestamp != exp:
            raise InvalidTokenError
        return userid
    except Exception:
        raise InvalidTokenError


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