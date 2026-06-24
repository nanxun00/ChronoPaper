import logging
from io import BytesIO
from fastapi import Body, Depends, FastAPI, HTTPException, status, Request, APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm

from typing import Annotated

from openai import BaseModel

from src.login.config import config
from src.models.auth import InsertUser, UpdateUser, SelectUserByUserID, select_user_by_email

ACCESS_TOKEN_EXPIRE_MINUTES = config["token"]["expires_time"]
ACCESS_TOKEN_DEFAULT_MINUTES = config["token"]["default_expires_time"]
# 创建一个FastAPI实例
# app = FastAPI()
login = APIRouter(prefix="")
router = login


custom_header_name = "X-Captcha-ID"



# 打印请求日志，可用于和客户端调试
async def log_request_details(request: Request):
    client_host = request.client.host
    client_port = request.client.port
    method = request.method
    url = request.url
    headers = request.headers
    body = None
    if request.form:
        body = await request.form()
    elif request.body:
        body = await request.body()

    print(f"Client: {client_host}:{client_port}")
    print(f"Method: {method} URL: {url}")
    print(f"Headers: {headers}")
    print(f"Body: {body if body else 'No Body'}")


'''
图片验证码
'''
from src.utils.captcha import generate_captcha
from src.utils.ttlcache import Cache, Error
from src.utils.email import send_email_captcha
import random
import string

_cache = Cache(max_size=300, ttl=300)  # 300个缓存，每个缓存5分钟
_email_captcha_cache = Cache(max_size=500, ttl=300) # 邮箱验证码缓存 5分钟

@login.post("/register/captcha")
async def send_register_captcha(
    background_tasks: BackgroundTasks,
    email: str = Body(..., embed=True)
):
    """发送邮箱注册验证码"""
    # 校验邮箱是否已被占用
    existing_user = select_user_by_email(email)
    if existing_user:
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    if _email_captcha_cache.is_full():
        raise HTTPException(status_code=429, detail="系统繁忙，请稍后再试")
    
    # 生成 6 位数字验证码
    captcha = ''.join(random.choices(string.digits, k=6))
    
    # 存入缓存
    _email_captcha_cache.add(email, captcha)
    
    # 异步发送邮件
    background_tasks.add_task(send_email_captcha, email, captcha)
    
    return {"message": "验证码发送请求已提交，请注意查收"}

@login.get("/captcha")
def get_captcha():
    if _cache.is_full():
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")

    captcha_id, captcha_text, captcha_image = generate_captcha()
    print(f"生成的验证码: {captcha_id} {captcha_text}")
    result = _cache.add(captcha_id, (captcha_text, captcha_image))
    if result != Error.OK:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")

    # 返回图片流
    buffer = BytesIO()
    captcha_image.save(buffer, format="PNG")
    buffer.seek(0)
    headers = {custom_header_name: captcha_id, "Cache-Control": "no-store"}
    # print(headers)
    return StreamingResponse(buffer, headers=headers, media_type="image/png")


'''
用户认证服务
'''
from src.utils.token import create_access_token
from src.api.deps import (
    TokenRoleId,
    TokenSchema,
    UserSchema,
    authenticate_user,
    get_current_active_user,
    get_roleid,
)


# 登录方法
@login.post("/token")
# async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), remember: bool | None = Body(None),
#                                  captcha_id: str | None = Body(None), captcha_input: str | None = Body(None),
#                                  log_details: None = Depends(log_request_details)) -> Token:
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(),
                                 log_details: None = Depends(log_request_details)):
    '''
    OAuth2PasswordRequestForm 是用以下几项内容声明表单请求体的类依赖项：

    username
    password
    scope、grant_type、client_id等可选字段。
    '''

    # 校验验证码
    # error, value = _cache.get(captcha_id)
    # if error != Error.OK:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired captcha ID")
    #
    # captcha_text = value[0]
    #
    # if not captcha_text:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired captcha ID")
    #
    # if captcha_text.upper() != captcha_input.upper():
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect captcha")

    # 用户认证
    user = authenticate_user(form_data.username, form_data.password)
    print("user",user)
    if not user:
        raise HTTPException(
            status_code=500,
            detail="用户名或者密码错误",
            headers={"WWW-Authenticate": "Bearer"}
        )
    # 使用 TOKEN_EXPIRES_TIME（默认 30 天），避免 15 分钟短 token 导致频繁 401
    access_token = create_access_token(
        data={"sub": user.username},
        encrypted_text=user.userid,
        expire_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    # 响应返回的内容应该包含 token_type。本例中用的是BearerToken，因此， Token 类型应为bearer。
    return TokenRoleId(Token=TokenSchema(access_token=access_token, token_type="bearer"), roleid=get_roleid(form_data.username))
    # return HTTPException(
    #         status_code=200,
    #         detail="登录成功",
    #         headers={"Authenticate": f"Bearer {access_token}"}
    # )


# 获取用户信息
@login.get("/users/me")
async def read_users_me(current_user: Annotated[UserSchema, Depends(get_current_active_user)]):
    '''
    Depends 在依赖注入系统中处理安全机制。
    此处把 current_user 的类型声明为 Pydantic 的 User 模型，这有助于在函数内部使用代码补全和类型检查。
    get_current_user 依赖项从子依赖项 oauth2_scheme 中接收 str 类型的 toke。
    FastAPI 校验请求中的 Authorization 请求头，核对请求头的值是不是由 Bearer + 令牌组成， 并返回令牌字符串；如果没有找到 Authorization 请求头，或请求头的值不是 Bearer + 令牌。FastAPI 直接返回 401 错误状态码（UNAUTHORIZED）。
    '''
    return current_user


'''
API网关服务
'''

import httpx

time_out = config["time_out"]
services = config["services"]

'''
services的key是服务名称，客户端在请求时传入服务名称，本网关再根据服务名称找到对应的服务地址
仅注册配置中的外部服务，避免 `/{service}/{path}` 抢占本地路由（如 /skills/）。
'''


async def _proxy_to_service(
    service: str,
    path: str,
    request: Request,
    current_user: UserSchema,
):
    '''
    !注意：网关并未将header转发给后端服务，这样比较简单。
    '''
    headers = {"userid": current_user.userid}
    client_request_data = await request.json()
    service_url = services[service]
    url = f"{service_url}/{path}"
    async with httpx.AsyncClient() as client:
        '''
        !注意：httpx.AsyncClient默认的timeout为5秒，在调用基于大模型的后端服务时经常超时，所以这里设置超时时间为30秒
        '''
        response = await client.post(url=url, json=client_request_data, headers=headers, timeout=time_out)
        return response.json()


def _register_service_gateway(service_name: str) -> None:
    async def gateway(
        path: str,
        request: Request,
        current_user: Annotated[UserSchema, Depends(get_current_active_user)],
    ):
        return await _proxy_to_service(service_name, path, request, current_user)

    login.add_api_route(
        f"/{service_name}/{{path:path}}",
        gateway,
        methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    )


for _service_name in services:
    _register_service_gateway(_service_name)

class register(BaseModel):
    username: str
    userid: str
    password: str
    email: str | None = None
    captcha: str | None = None

class ForgotPasswordCaptcha(BaseModel):
    userid: str
    email: str

class ResetPassword(BaseModel):
    userid: str
    email: str
    captcha: str
    new_password: str

@login.post("/forgot-password/captcha")
async def send_forgot_password_captcha(
    background_tasks: BackgroundTasks,
    data: ForgotPasswordCaptcha
):
    """发送找回密码验证码"""
    # 1. 校验账号和邮箱是否匹配
    user = SelectUserByUserID(data.userid)
    if not user:
        raise HTTPException(status_code=400, detail="该账号不存在")
    
    if user.email != data.email:
        raise HTTPException(status_code=400, detail="账号与邮箱不匹配")

    if _email_captcha_cache.is_full():
        raise HTTPException(status_code=429, detail="系统繁忙，请稍后再试")
    
    # 2. 生成 6 位数字验证码
    captcha = ''.join(random.choices(string.digits, k=6))
    
    # 3. 存入缓存（Key 使用 email + ":forgot" 以防和注册验证码冲突，或者直接用 email）
    # 这里为了简单直接用 email，因为一个人同一时间通常只做一个操作
    _email_captcha_cache.add(data.email, captcha)
    
    # 4. 异步发送邮件
    background_tasks.add_task(send_email_captcha, data.email, captcha)
    
    return {"message": "验证码发送成功，请查收"}

@login.post("/forgot-password/reset")
async def reset_password(data: ResetPassword):
    """重置密码"""
    # 1. 校验验证码
    err, cached_captcha = _email_captcha_cache.get(data.email)
    if err != Error.OK:
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
    if cached_captcha != data.captcha:
        raise HTTPException(status_code=400, detail="验证码错误")

    # 2. 校验账号邮箱匹配（双重保险）
    user = SelectUserByUserID(data.userid)
    if not user or user.email != data.email:
        raise HTTPException(status_code=400, detail="身份验证失败")

    # 3. 更新密码
    result = UpdateUser(data.userid, data.new_password)
    if result:
        logging.info(f"用户 {data.userid} 重置密码成功")
        return {"message": "密码重置成功，请重新登录"}
    else:
        raise HTTPException(status_code=500, detail="密码重置失败，请稍后再试")

@login.post("/register")
async def register(register: register):
    # 1. 校验验证码（优先级最高，先验证身份）
    if register.email and register.captcha:
        err, cached_captcha = _email_captcha_cache.get(register.email)
        if err != Error.OK:
            raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
        if cached_captcha != register.captcha:
            raise HTTPException(status_code=400, detail="验证码错误")

    # 2. 校验账号是否已存在
    existing_user_id = SelectUserByUserID(register.userid)
    if existing_user_id:
        raise HTTPException(status_code=400, detail="该账号已被占用，请更换")

    # 3. 校验邮箱是否已被占用
    if register.email:
        existing_email = select_user_by_email(register.email)
        if existing_email:
            raise HTTPException(status_code=400, detail="该邮箱已被注册，请直接登录")

    # 4. 执行插入
    result = InsertUser(
        username=register.username, 
        userid=register.userid, 
        password=register.password,
        email=register.email
    )
    if result:
        logging.info(f"用户 {register.userid} 注册成功")
        return {"message": "注册成功！"}
    else:
        # 兜底错误，通常是数据库连接问题或未预料的冲突
        raise HTTPException(status_code=500, detail="注册失败，请稍后再试")


class change(BaseModel):
    userid: str
    password: str
    new_password: str

@login.post("/change-password")
async def change_password(change: change):
    result = authenticate_user(change.userid, change.password)
    if not result:
        return HTTPException(status_code=500, detail="账户或密码输入错误！")
    else:
        result = UpdateUser(change.userid, change.new_password)
        if result:
            logging.info("修改密码成功！")
            return HTTPException(status_code=200, detail="修改密码成功！")
        else:
            return HTTPException(status_code=500, detail="修改密码失败！")

if __name__ == "__main__":
    import uvicorn

    # 交互式API文档地址：
    # http://127.0.0.1:8000/docs/
    # http://127.0.0.1:8000/redoc/
    # uvicorn.run(app, host="0.0.0.0", port=8000)