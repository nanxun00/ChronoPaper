-- 清空所有业务表后重建（仅在需要重置时使用）
-- DataGrip：选中 chronopaper 库后执行

USE `chronopaper`;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `literature_entries`;
DROP TABLE IF EXISTS `crawl_task_runs`;
DROP TABLE IF EXISTS `crawl_tasks`;
DROP TABLE IF EXISTS `papers`;
DROP TABLE IF EXISTS `users`;
SET FOREIGN_KEY_CHECKS = 1;

-- 然后执行 init_chronopaper.sql 中的建表段落
