# 使用基础镜像
FROM tiangolo/uvicorn-gunicorn:python3.10

# 添加维护者信息
LABEL maintainer="nanxun"

RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
#创建一个硬链接，将上海时区信息链接到容器的 /etc/localtime，以设置容器的时区为上海时区。
RUN echo 'Asia/Shanghai' > /etc/timezone

# 设置工作目录
WORKDIR /app

# 将当前目录下的所有文件复制到容器内的 /app 目录中
COPY . /app

# 安装依赖，指定国内镜像源并延长超时时间
RUN pip install --no-cache-dir --upgrade --timeout 60000 -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 将应用代码复制到容器的工作目录
COPY . /app

# 声明容器运行时将监听的端口
EXPOSE 19037

# 指定容器启动时运行的命令
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "19037"]