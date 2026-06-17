"""SQLAlchemy engine、Session 与 Base。"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from src.settings import get_settings

settings = get_settings()

Base = declarative_base()

engine = create_engine(
    settings.mysql_url(),
    echo=False,
    pool_size=8,
    pool_recycle=60 * 30,
)

SessionLocal = sessionmaker(bind=engine)


def get_session():
    return SessionLocal()


def implemented_orm_models():
    """已实现业务使用的 ORM（不含 Idea / LaTeX / favorite 等待实现模块）。"""
    from src.models.user import UserModel
    from src.models.paper import Paper
    from src.models.crawl import CrawlTask, CrawlTaskRun
    from src.models.literature import LiteratureEntry

    return [UserModel, Paper, CrawlTask, CrawlTaskRun, LiteratureEntry]


def ensure_mysql_database() -> None:
    """若 chronopaper 库不存在则创建（需账号具备 CREATE DATABASE 权限）。"""
    from urllib.parse import quote_plus

    user = quote_plus(settings.mysql_user)
    password = quote_plus(settings.mysql_password)
    server_url = (
        f"mysql+pymysql://{user}:{password}"
        f"@{settings.mysql_host}:{settings.mysql_port}/?charset=utf8mb4"
    )
    db_name = settings.mysql_db
    bootstrap = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with bootstrap.connect() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
    bootstrap.dispose()


def init_db() -> None:
    """启动时创建已实现功能所需的 MySQL 表。"""
    from src.utils.logging_config import setup_logger

    log = setup_logger("ChronoPaper.db", console=True)

    try:
        ensure_mysql_database()
    except Exception as exc:
        log.warning("Skip auto-create database (use existing DB): %s", exc)

    models = implemented_orm_models()
    tables = [model.__table__ for model in models]
    expected = sorted(t.name for t in tables)

    Base.metadata.create_all(engine, tables=tables, checkfirst=True)

    existing = sorted(inspect(engine).get_table_names())
    created = [name for name in expected if name in existing]
    missing = [name for name in expected if name not in existing]

    if missing:
        log.error("MySQL tables missing after init: %s", ", ".join(missing))
        raise RuntimeError(f"Failed to create tables: {', '.join(missing)}")

    log.info(
        "MySQL ready database=%s tables=[%s]",
        settings.mysql_db,
        ", ".join(created),
    )

    from src.models.user import ensure_default_admin

    try:
        ensure_default_admin()
        log.info("Default admin user ready (admin / 123456)")
    except Exception as exc:
        log.warning("Could not seed admin user: %s", exc)
