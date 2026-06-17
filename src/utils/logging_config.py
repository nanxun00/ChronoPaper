import logging
import os
from datetime import datetime


DATETIME = datetime.now().strftime('%Y-%m-%d-%H%M%S')
# DATETIME = "debug" # 为了方便，调试的时候输出到 debug.log 文件
# TODO
LOG_FILE = f'saves/log/project-{DATETIME}.log'

def setup_logger(name, level=logging.DEBUG, console=False):
    '''
        配置具有指定名称和日志文件的记录器
        参数：
            - name: 记录器的名称
            - level: 日志级别，默认为debug
            - console: 是否将日志输出到控制台，默认为False
        返回值：
            - logger: 配置好的记录器对象
    '''
    # TODO
    os.makedirs("saves/log", exist_ok=True)

    """Function to setup logger with the given name and log file."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 清除已有的 Handler(处理器)，防止重复添加
    if logger.hasHandlers():
        logger.handlers.clear()

    # 文件处理器，用于将日志记录到文件
    file_handler = logging.FileHandler(LOG_FILE,encoding='utf-8') #设置日志的编码格式为utf-8
    file_handler.setLevel(level)

    # 日志格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 控制台处理器，可以将日志添加到控制台
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


# Setup the root logger
logger = setup_logger('Yuxi')

# If you want to disable logging from external libraries
# logging.getLogger('some_external_library').setLevel(logging.CRITICAL)
