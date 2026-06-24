"""用户 ORM 与数据访问。"""
from sqlalchemy import Column, Integer, String

from src.models.base import Base, SessionLocal
from src.utils.password import get_password_hash
import logging

logger = logging.getLogger("ChronoPaper.user")

ADMIN_BCRYPT_HASH = "$2b$12$XbGyrM6BlwUSENpc0lXxIOlFsNSXJIrN/dCoa2LVOZS/SMXXIkPri"


class UserModel(Base):
    __tablename__ = "users"

    userid = Column(String(255), primary_key=True)
    username = Column(String(255), nullable=False)
    email = Column(String(255), unique=True)
    full_name = Column(String(255))
    password = Column(String(255), nullable=False)
    roleid = Column(Integer, default=0)


def insert_user(username: str, userid: str, password: str, email: str = None) -> bool:
    session = SessionLocal()
    try:
        user = UserModel(
            userid=userid,
            username=username,
            email=email,
            password=get_password_hash(password),
            roleid=0,
        )
        session.add(user)
        session.commit()
        return True
    except Exception as e:
        logger.error(f"Error inserting user: {str(e)}")
        session.rollback()
        return False
    finally:
        session.close()


def update_user(userid: str, password: str) -> bool:
    session = SessionLocal()
    try:
        user = session.query(UserModel).filter_by(userid=userid).first()
        if not user:
            return False
        user.password = get_password_hash(password)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def _detach_user(session, user: UserModel | None) -> UserModel | None:
    if user is None:
        return None
    session.expunge(user)
    return user


def select_user_by_userid(userid: str):
    session = SessionLocal()
    try:
        user = session.query(UserModel).filter_by(userid=userid).first()
        return _detach_user(session, user)
    finally:
        session.close()


def select_user_by_username(username: str):
    session = SessionLocal()
    try:
        user = session.query(UserModel).filter_by(username=username).first()
        return _detach_user(session, user)
    finally:
        session.close()


def ensure_default_admin() -> None:
    """启动时确保 admin 账号存在（密码 123456）。"""
    session = SessionLocal()
    try:
        existing = session.query(UserModel).filter_by(userid="admin").first()
        if existing:
            return
        session.add(
            UserModel(
                userid="admin",
                username="admin",
                password=ADMIN_BCRYPT_HASH,
                roleid=1,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def select_user_by_email(email: str):
    session = SessionLocal()
    try:
        user = session.query(UserModel).filter_by(email=email).first()
        return _detach_user(session, user)
    finally:
        session.close()


# Backward-compatible aliases
InsertUser = insert_user
UpdateUser = update_user
SelectUserByUserID = select_user_by_userid
SelectUserByEmail = select_user_by_email
SelectUserByUserName = select_user_by_username
DbSession = SessionLocal
