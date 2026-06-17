'''
处理用户
'''
from pydantic import BaseModel
from typing import Union
import os
import json

from src.login.user_sql import SelectUserByUserName, SelectUserByUserID


# 用户实体
class User(BaseModel):
    userid: str
    username: str
    email: Union[str, None] = None
    full_name: Union[str, None] = None
    disabled: Union[bool, None] = None


class UserInDB(User):
    hashed_password: str


def get_user(username: str):
    user = SelectUserByUserName(username=username)
    if user is None:
        return None
    else:
        return UserInDB(username=user.username,userid=user.userid,hashed_password=user.password)

def get_userByID(userid: str):
    user = SelectUserByUserID(userid=userid)
    if user is None:
        return None
    else:
        return UserInDB(username=user.username,userid=user.userid,hashed_password=user.password)

def get_roleid(username: str):
    user = SelectUserByUserName(username=username)
    if user is None:
        return None
    else:
        return user.roleid

'''
UserInDB(**user_dict) 是指：

直接把 user_dict 的键与值当作关键字参数传递，等效于：

UserInDB(
    username = user_dict["username"],
    email = user_dict["email"],
    full_name = user_dict["full_name"],
    disabled = user_dict["disabled"],
    hashed_password = user_dict["hashed_password"],
)
'''

from src.utils.password import verify_password


# 通过用户id和密码认证用户
def authenticate_user(username: str, password: str):
    print(username, password)

    user = get_user(username)
    if user is None:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# 通过用户id和密码认证用户
def authenticate_userByID(userid: str, password: str):
    # print(userid, password)

    user = get_userByID(userid)
    if user is None:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


'''
处理token
'''


# Token实体
class Token(BaseModel):
    access_token: str
    token_type: str

class Token_roleid():
    Token: Token
    roleid: str

    def __init__(self, Token: Token, roleid: str):
        self.Token = Token
        self.roleid = roleid

class TokenData(BaseModel):
    username: str | None = None


from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status

# 使用 OAuth2 的 Password 流以及 Bearer 令牌（Token）。
# tokenUrl="token" 指向的是暂未创建的相对 URL token。这个相对 URL 相当于 ./token。
# 此设置将会要求客户端把 username 与password 发送至 API 中指定的 URL：http://127.0.0.1:8000/token 。
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

from src.utils.token import decode_access_token


# 根据token获取当前登录的用户信息
# 该函数接收 str 类型的令牌，并返回 Pydantic 的 User 模型
async def get_current_user(token: str = Depends(oauth2_scheme)):
    '''
    安全和依赖注入的代码只需要写一次。各个端点可以使用同一个安全系统。
    '''
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        userid = decode_access_token(token)
        if userid is None or userid == "":
            raise credentials_exception
        user = get_userByID(userid=userid)
        if user is None:
            raise credentials_exception
        return user
    except Exception:
        raise credentials_exception


# 获取当前登录用户信息，并检查是否禁用
async def get_current_active_user(current_user: User = Depends(get_current_user)):
    '''
    在端点中，只有当用户存在、通过身份验证、且状态为激活时，才能获得该用户信息。
    '''
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user



if __name__ == '__main__':
    pass