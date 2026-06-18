"""API dependencies: database session and authentication."""
import logging
from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.base import SessionLocal
from src.models.auth import select_user_by_userid, select_user_by_username
from src.utils.password import verify_password
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from src.utils.token import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")
logger = logging.getLogger("ChronoPaper.auth")


class UserSchema(BaseModel):
    userid: str
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(UserSchema):
    hashed_password: str


class TokenSchema(BaseModel):
    access_token: str
    token_type: str


class TokenRoleId:
    def __init__(self, Token: TokenSchema, roleid: str):
        self.Token = Token
        self.roleid = roleid


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_by_username(username: str) -> UserInDB | None:
    user = select_user_by_username(username)
    if user is None:
        return None
    return UserInDB(username=user.username, userid=user.userid, hashed_password=user.password)


def get_user_by_id(userid: str) -> UserInDB | None:
    user = select_user_by_userid(userid)
    if user is None:
        return None
    return UserInDB(username=user.username, userid=user.userid, hashed_password=user.password)


def get_roleid(username: str):
    user = select_user_by_username(username)
    return user.roleid if user else None


def authenticate_user(username: str, password: str):
    user = get_user_by_username(username)
    if user is None or not verify_password(password, user.hashed_password):
        return False
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        userid = decode_access_token(token)
        if not userid:
            raise credentials_exception
        user = get_user_by_id(userid)
        if user is None:
            logger.warning("JWT valid but user not found in DB: userid=%s", userid)
            raise credentials_exception
        return user
    except ExpiredSignatureError as exc:
        logger.info("JWT expired: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc) or "登录已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError as exc:
        logger.warning("JWT invalid: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc) or "无效的登录凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("JWT auth failed: %s", exc, exc_info=True)
        raise credentials_exception


async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
