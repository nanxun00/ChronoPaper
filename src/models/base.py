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
    from src.models.auth import UserModel
    from src.models.literature import LiteratureEntry, Paper
    from src.models.crawl import CrawlTask, CrawlTaskRun
    from src.models.chat import ChatConversation, ChatMessage

    return [UserModel, Paper, CrawlTask, CrawlTaskRun, LiteratureEntry, ChatConversation, ChatMessage]


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


def repair_chat_conversation_fk(engine, log) -> None:
    """移除 chat_conversation 上指向 users 的不兼容外键（charset/collation 不一致）。"""
    inspector = inspect(engine)
    if "chat_conversation" not in inspector.get_table_names():
        return
    for fk in inspector.get_foreign_keys("chat_conversation"):
        if fk.get("referred_table") == "users":
            fk_name = fk.get("name") or "chat_conversation_ibfk_1"
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE chat_conversation DROP FOREIGN KEY `{fk_name}`"))
                log.info("Dropped incompatible chat_conversation FK: %s", fk_name)
            except Exception as exc:
                log.warning("Could not drop chat_conversation FK %s: %s", fk_name, exc)


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
    if "doi" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN doi VARCHAR(256) NULL")
    if "openalex_id" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN openalex_id VARCHAR(64) NULL")
    if "venue_rank" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN venue_rank VARCHAR(8) NULL")
    if "journal_if" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN journal_if FLOAT NULL")
    if "jcr_quartile" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN jcr_quartile VARCHAR(8) NULL")
    if "quality_score" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN quality_score FLOAT NULL")
    if "llm_innovation_score" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN llm_innovation_score FLOAT NULL")
    if "llm_experiment_score" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN llm_experiment_score FLOAT NULL")
    if "quality_assessed_at" not in paper_cols:
        alters.append("ALTER TABLE papers ADD COLUMN quality_assessed_at DATETIME NULL")

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
        if "openalex_venue_types" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN openalex_venue_types VARCHAR(64) NOT NULL DEFAULT 'conference,journal'")
        if "openalex_ccf_ranks" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN openalex_ccf_ranks VARCHAR(32) NOT NULL DEFAULT 'A,B,C'")
        if "openalex_year_from" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN openalex_year_from INT NULL")
        if "openalex_year_to" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN openalex_year_to INT NULL")
        if "openalex_venue_names" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN openalex_venue_names VARCHAR(1024) NOT NULL DEFAULT ''")
        if "min_semantic_score" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN min_semantic_score FLOAT NOT NULL DEFAULT 50")
        if "min_quality_score" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN min_quality_score FLOAT NOT NULL DEFAULT 0")
        if "enable_quality_filter" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN enable_quality_filter TINYINT(1) NOT NULL DEFAULT 0")
        if "enable_smart_planning" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN enable_smart_planning TINYINT(1) NOT NULL DEFAULT 0")
        if "plan_summary" not in task_cols:
            alters.append(
                "ALTER TABLE crawl_tasks ADD COLUMN plan_summary VARCHAR(2048) NOT NULL DEFAULT ''"
            )
        if "verified_suggestions_json" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN verified_suggestions_json TEXT NULL")
        if "planning_status" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN planning_status VARCHAR(16) NOT NULL DEFAULT 'none'")
        if "planning_error" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN planning_error VARCHAR(512) NOT NULL DEFAULT ''")
        if "crawl_mode" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN crawl_mode VARCHAR(16) NOT NULL DEFAULT 'latest'")
        if "auto_run_on_ready" not in task_cols:
            alters.append("ALTER TABLE crawl_tasks ADD COLUMN auto_run_on_ready TINYINT(1) NOT NULL DEFAULT 0")

    if "literature_entries" in inspector.get_table_names():
        entry_cols = {c["name"] for c in inspector.get_columns("literature_entries")}
        if "semantic_score" not in entry_cols:
            alters.append("ALTER TABLE literature_entries ADD COLUMN semantic_score FLOAT NULL")
        if "quality_score" not in entry_cols:
            alters.append("ALTER TABLE literature_entries ADD COLUMN quality_score FLOAT NULL")
        if "pool_type" not in entry_cols:
            alters.append("ALTER TABLE literature_entries ADD COLUMN pool_type VARCHAR(16) NULL")
        if "review_status" not in entry_cols:
            alters.append(
                "ALTER TABLE literature_entries ADD COLUMN review_status VARCHAR(16) NOT NULL DEFAULT 'approved'"
            )

    table_names = set(inspector.get_table_names())
    if "chat_message" in table_names:
        alters.append(
            "ALTER TABLE chat_message CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    if "chat_conversation" in table_names:
        alters.append(
            "ALTER TABLE chat_conversation CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )

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

    repair_chat_conversation_fk(engine, log)
    Base.metadata.create_all(engine, tables=tables, checkfirst=True)

    existing = sorted(inspect(engine).get_table_names())
    created = [name for name in expected if name in existing]
    missing = [name for name in expected if name not in existing]

    if missing:
        log.error("MySQL tables missing after init: %s", ", ".join(missing))
        raise RuntimeError(f"Failed to create tables: {', '.join(missing)}")

    log.info(
        "MySQL ready database=%s %s tables=[%s]",
        settings.mysql_db,
        settings.mysql_summary(),
        ", ".join(created),
    )

    migrate_schema(engine, log)

    from src.models.auth import ensure_default_admin

    try:
        ensure_default_admin()
        log.info("Default admin user ready (admin / 123456)")
    except Exception as exc:
        log.warning("Could not seed admin user: %s", exc)
