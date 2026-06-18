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


def migrate_schema(engine, log) -> None:
    """为已存在库补充新列（create_all 不会 ALTER 旧表）。"""
    inspector = inspect(engine)
    if "papers" not in inspector.get_table_names():
        return

    paper_cols = {c["name"] for c in inspector.get_columns("papers")}
    alters = []
    if "source" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN source VARCHAR(32) NOT NULL DEFAULT 'arxiv'")
    if "venue" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN venue VARCHAR(255) NULL")
    if "venue_type" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN venue_type VARCHAR(64) NULL")
    if "citation_count" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN citation_count INT NULL")
    if "acceptance_status" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN acceptance_status VARCHAR(64) NULL")
    if "review_rating" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN review_rating FLOAT NULL")
    if "openreview_id" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN openreview_id VARCHAR(128) NULL")

    arxiv_col = next((c for c in inspector.get_columns("papers") if c["name"] == "arxiv_id"), None)
    if arxiv_col and str(arxiv_col.get("type")).endswith("64"):
        alters.append("ALTER TABLE papers MODIFY COLUMN arxiv_id VARCHAR(128) NOT NULL")
        if "literature_entries" in inspector.get_table_names():
            alters.append("ALTER TABLE literature_entries MODIFY COLUMN arxiv_id VARCHAR(128) NOT NULL")

    if "crawl_tasks" in inspector.get_table_names():
        task_cols = {c["name"] for c in inspector.get_columns("crawl_tasks")}
        if "sources" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN sources VARCHAR(128) NOT NULL DEFAULT 'arxiv'")
        if "openreview_venues" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN openreview_venues VARCHAR(1024) NOT NULL DEFAULT ''")

    for ddl in alters:
        try:
            with engine.begin() as conn:
                conn.execute(text(ddl))
            log.info("Schema migrated: %s", ddl.split("ADD COLUMN")[-1].split("MODIFY")[-1][:40])
        except Exception as exc:
            log.warning("Schema migration skipped: %s (%s)", ddl[:60], exc)


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

    migrate_schema(engine, log)

    from src.models.user import ensure_default_admin

    try:
        ensure_default_admin()
        log.info("Default admin user ready (admin / 123456)")
    except Exception as exc:
        log.warning("Could not seed admin user: %s", exc)
