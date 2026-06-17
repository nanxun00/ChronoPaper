from src.core import DataBaseManager
from src.core.retriever import Retriever
from src.models import select_model
from src.config import Config
from src.utils import setup_logger

logger = setup_logger("Startup")


class Startup:
    def __init__(self):
        self.start()    # 调用start()方法

    def start(self):
        self.config = Config()
        self.model = select_model(self.config)  # 选择模型
        self.dbm = DataBaseManager(self.config) # 创建数据库管理器
        self.retriever = Retriever(self.config, self.dbm, self.model)   # 创建检索器

    def restart(self):
        logger.info("Restarting...")
        self.start()
        logger.info("Restarted")


startup = Startup()