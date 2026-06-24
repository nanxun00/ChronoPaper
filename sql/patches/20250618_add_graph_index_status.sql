-- 为 papers 表增加图谱入库状态（向量入库与 GraphRAG 分离追踪）
USE `chronopaper`;

ALTER TABLE `papers`
  ADD COLUMN `graph_index_status` VARCHAR(32) NULL DEFAULT NULL COMMENT 'pending|indexing|ok|failed|skipped' AFTER `parse_status`,
  ADD COLUMN `graph_index_error` VARCHAR(512) NULL DEFAULT NULL AFTER `graph_index_status`;

-- 历史「已向量入库」记录：标记为待补建图谱（需 Celery 执行 graph_index_paper）
UPDATE `papers`
SET `graph_index_status` = 'pending'
WHERE `parse_status` = 'indexed'
  AND (`graph_index_status` IS NULL OR `graph_index_status` = '');
