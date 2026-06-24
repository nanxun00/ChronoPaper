-- ChronoPaper 建表脚本（兼容 MySQL 5.7 / 8.0）
--
-- DataGrip 用法：
--   1. 左侧选中 chronopaper 库（或先执行下面两行建库）
--   2. 不要全选整文件一次执行；按「-- [1]」～「-- [6]」分段选中，逐段 Run
--
-- 命令行：mysql -u root -p chronopaper < sql/init_chronopaper.sql

CREATE DATABASE IF NOT EXISTS `chronopaper`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `chronopaper`;

-- [1] 用户表
CREATE TABLE IF NOT EXISTS `users` (
  `userid`     VARCHAR(255) NOT NULL,
  `username`   VARCHAR(255) NOT NULL,
  `email`      VARCHAR(255) NULL,
  `full_name`  VARCHAR(255) NULL,
  `password`   VARCHAR(255) NOT NULL,
  `roleid`     INT NULL DEFAULT 0,
  PRIMARY KEY (`userid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- [2] 论文元数据（TEXT 不可写 DEFAULT，默认值由应用层写入）
CREATE TABLE IF NOT EXISTS `papers` (
  `arxiv_id`           VARCHAR(128) NOT NULL,
  `source`             VARCHAR(32)  NOT NULL DEFAULT 'arxiv',
  `title`              LONGTEXT     NOT NULL,
  `authors`            LONGTEXT     NOT NULL,
  `abstract`           LONGTEXT     NOT NULL,
  `categories`         LONGTEXT     NOT NULL,
  `published_at`       DATETIME     NULL,
  `abs_url`            VARCHAR(512) NULL,
  `pdf_url`            VARCHAR(512) NULL,
  `pdf_path`           VARCHAR(512) NULL,
  `parse_status`       VARCHAR(32)  NOT NULL DEFAULT 'pending',
  `venue`              VARCHAR(255) NULL,
  `venue_type`         VARCHAR(64)  NULL,
  `citation_count`     INT          NULL,
  `acceptance_status`  VARCHAR(64)  NULL,
  `review_rating`      FLOAT        NULL,
  `openreview_id`      VARCHAR(128) NULL,
  `created_at`         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`arxiv_id`),
  KEY `ix_papers_published_at` (`published_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- [3] 抓取任务
CREATE TABLE IF NOT EXISTS `crawl_tasks` (
  `id`                  INT          NOT NULL AUTO_INCREMENT,
  `user_id`             VARCHAR(255) NOT NULL,
  `name`                VARCHAR(255) NOT NULL,
  `intent_text`         LONGTEXT     NOT NULL,
  `sources`             VARCHAR(128) NOT NULL DEFAULT 'arxiv',
  `categories`          VARCHAR(512) NOT NULL DEFAULT '',
  `openreview_venues`   VARCHAR(1024) NOT NULL DEFAULT '',
  `keywords`            VARCHAR(512) NOT NULL DEFAULT '',
  `visibility`          VARCHAR(16)  NOT NULL DEFAULT 'public',
  `schedule_time`       VARCHAR(8)   NULL,
  `min_match_score`     FLOAT        NOT NULL DEFAULT 40,
  `max_papers_per_run`  INT          NOT NULL DEFAULT 50,
  `enabled`             TINYINT(1)   NOT NULL DEFAULT 1,
  `last_run_at`         DATETIME     NULL,
  `created_at`          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_crawl_tasks_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- [4] 抓取执行记录
CREATE TABLE IF NOT EXISTS `crawl_task_runs` (
  `id`           INT          NOT NULL AUTO_INCREMENT,
  `task_id`      INT          NOT NULL,
  `status`       VARCHAR(32)  NOT NULL DEFAULT 'waiting',
  `trigger_type` VARCHAR(16)  NOT NULL DEFAULT 'manual',
  `progress`     INT          NOT NULL DEFAULT 0,
  `stats_json`   LONGTEXT     NOT NULL,
  `log_text`     LONGTEXT     NOT NULL,
  `started_at`   DATETIME     NULL,
  `finished_at`  DATETIME     NULL,
  PRIMARY KEY (`id`),
  KEY `ix_crawl_task_runs_task_id` (`task_id`),
  CONSTRAINT `fk_crawl_task_runs_task_id`
    FOREIGN KEY (`task_id`) REFERENCES `crawl_tasks` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- [5] 文献列表
CREATE TABLE IF NOT EXISTS `literature_entries` (
  `id`          INT          NOT NULL AUTO_INCREMENT,
  `arxiv_id`    VARCHAR(128) NOT NULL,
  `user_id`     VARCHAR(255) NOT NULL DEFAULT '',
  `visibility`  VARCHAR(16)  NOT NULL,
  `match_score` FLOAT        NULL,
  `review_status` VARCHAR(16) NOT NULL DEFAULT 'approved',
  `task_id`     INT          NULL,
  `run_id`      INT          NULL,
  `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_literature_scope` (`arxiv_id`, `user_id`, `visibility`),
  KEY `ix_literature_entries_arxiv_id` (`arxiv_id`),
  KEY `ix_literature_entries_user_id` (`user_id`),
  CONSTRAINT `fk_literature_entries_arxiv_id`
    FOREIGN KEY (`arxiv_id`) REFERENCES `papers` (`arxiv_id`),
  CONSTRAINT `fk_literature_entries_task_id`
    FOREIGN KEY (`task_id`) REFERENCES `crawl_tasks` (`id`),
  CONSTRAINT `fk_literature_entries_run_id`
    FOREIGN KEY (`run_id`) REFERENCES `crawl_task_runs` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- [6] 聊天会话
CREATE TABLE IF NOT EXISTS `chat_conversation` (
  `conv_id`        VARCHAR(64)  NOT NULL,
  `user_id`        VARCHAR(255) NOT NULL,
  `title`          VARCHAR(255) NOT NULL DEFAULT '新对话',
  `bind_paper_id`  VARCHAR(128) NULL,
  `bind_doc_id`    VARCHAR(64)  NULL,
  `model_name`     VARCHAR(64)  NOT NULL DEFAULT '',
  `system_prompt`  LONGTEXT     NULL,
  `created_at`     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `last_active_at` DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`conv_id`),
  KEY `idx_chat_conv_user_time` (`user_id`, `last_active_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- [7] 聊天消息
CREATE TABLE IF NOT EXISTS `chat_message` (
  `msg_id`       VARCHAR(64)  NOT NULL,
  `conv_id`      VARCHAR(64)  NOT NULL,
  `role`         VARCHAR(16)  NOT NULL,
  `content`      LONGTEXT     NOT NULL,
  `total_tokens` INT          NOT NULL DEFAULT 0,
  `metadata`     JSON         NULL,
  `created_at`   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`msg_id`),
  KEY `idx_chat_msg_conv_sort` (`conv_id`, `created_at`),
  CONSTRAINT `fk_chat_message_conv_id`
    FOREIGN KEY (`conv_id`) REFERENCES `chat_conversation` (`conv_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- [8] 默认管理员 admin / 123456
INSERT INTO `users` (`userid`, `username`, `password`, `roleid`)
VALUES ('admin', 'admin', '$2b$12$XbGyrM6BlwUSENpc0lXxIOlFsNSXJIrN/dCoa2LVOZS/SMXXIkPri', 1)
ON DUPLICATE KEY UPDATE
  `username` = VALUES(`username`),
  `password` = VALUES(`password`),
  `roleid`   = VALUES(`roleid`);

SHOW TABLES;
