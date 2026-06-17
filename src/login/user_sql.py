from logging import ERROR
import os

from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

from src.utils.password import get_password_hash
from src.settings import get_settings

settings = get_settings()

Base = declarative_base()

engine = create_engine(
    settings.mysql_url(),
    echo=False,
    pool_size=8,
    pool_recycle=60 * 30,
)


class User(Base):
    __tablename__ = 'users'

    userid = Column(String(255), primary_key=True)
    username = Column(String(255), nullable=False)
    email = Column(String(255))
    full_name = Column(String(255))
    password = Column(String(255), nullable=False)
    roleid = Column(Integer, default=0)

    def __init__(self, userid, username='', password='', email='', full_name='', roleid=0):
        self.userid = userid
        self.username = username
        self.email = email
        self.full_name = full_name
        self.password = get_password_hash(password)
        self.roleid = roleid

DbSession = sessionmaker(bind=engine)
session = DbSession()


def InsertUser(username,userid,password):
    try:
        userInsert = User(userid, username, password)
        session.add(userInsert)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        return False

def UpdateUser(userid, password):
    try:
        users = session.query(User).filter_by(userid=userid).first()
        users.password = get_password_hash(password)
        session.add(users)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        return False


def SelectUserByUserID(userid):
    try:
        users = session.query(User).filter_by(userid=userid).all()
        if not users:
            return None
        else:
            return users[0]
    except Exception as e:
        session.rollback()
        raise e

def SelectUserByUserName(username):
    try:
        users = session.query(User).filter_by(username=username).all()
        if not users:
            return None
        else:
            return users[0]
    except Exception as e:
        session.rollback()
        raise e

if __name__ == '__main__':
    InsertUser('admin','123456','123456')
