from fastapi import APIRouter

base = APIRouter()

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi import Request, Body
from src.core import HistoryManager
from src.utils.logging_config import setup_logger
from src.core.startup import startup

logger = setup_logger("server-base")

# 当用户访问根路径的时候会被调用，返回了一个json响应
@base.get("/")
async def route_index():
    '''
        处理根路径的get请求

        返回：
            一个包含消息的字典，用于响应客户端的请求
    '''
    return {"message": "You Got It!"}


@base.get("/config")
def get_config():
    # 返回当前应用的配置信息
    return startup.config

@base.post("/config")
async def update_config(key=Body(...), value=Body(...)):
    '''
        更新配置信息
        参数：
            - key(str): 配置项的键，使用body(...)标记参数为请求体的一部分，表示客户端请求中必须包含此参数
            - value(any): 与给定键关联的值，这可以是任何可以存储在字典的值
        返回：
            - dict； 更新后的完整配置字典，这为调用者提供了当前的配置状态
    '''
    startup.config[key] = value
    startup.config.save()
    return startup.config

@base.post("/restart")
async def restart():
    startup.restart()
    return {"message": "Restarted!"}

@base.get("/log")
def get_log():
    '''
        获取日志文件的末尾部分
        本函数读取日志文件的最后1000行，并将其作为字符串返回
        这是为了在不是加过多的负载的情况下，提供最近的日志信息
        返回：
            日志信息的字典
    '''
    from src.utils.logging_config import LOG_FILE
    from collections import deque

    with open(LOG_FILE, 'r') as f:
        last_lines = deque(f, maxlen=1000)

    log = ''.join(last_lines)
    return {"log": log}


