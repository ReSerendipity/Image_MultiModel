# 数据字典（DATABASE_SCHEMA.md）

> 对应数据治理评估报告 §4.3（数据字典缺失）。本文件为 `history_db.py` 的权威字段说明，
> 是所有数据消费者（前端、统计、血缘追溯）的单一事实来源。

## 存储位置

- 主库：`data/history.db`（SQLite，WAL 模式）
- 备份：`data/history.backup.<ts>.db`（由 `HistoryDB.backup()` 经 `VACUUM INTO` 生成，保留最近 7 个）
- 全文索引：FTS5 `tasks_fts`（`prompt` / `negative_prompt` / `tags`）

## ERD（文本）

```
tasks (1) ──< (N) outputs        tasks.task_id = outputs.task_id
tasks (1) ──< (N) presets        presets 引用 tasks 的 generation_config
```

## 表：`tasks`

| 列 | 类型 | 约束 | 说明 | 血缘/治理 |
|----|------|------|------|----------|
| task_id | TEXT | PK | 任务 ID（uuid4 hex 前 16 位；注：config 声明 `id_format: ulid` 但未实际启用） | — |
| engine | TEXT | | 引擎名（config.models.engines 键） | — |
| mode | TEXT | | `txt2img` / `batch` | — |
| prompt | TEXT | | 正向提示词 | FTS |
| negative_prompt | TEXT | | 负向提示词 | FTS |
| generation_config | TEXT(JSON) | | 完整生成参数（seed/steps/cfg/尺寸/LoRA 栈等） | 反序列化后使用 |
| tags | TEXT(JSON) | | 标签列表 | FTS |
| status | TEXT | | `pending/processing/completed/failed/cancelled`（+ `interrupted`） | 状态机 |
| error | TEXT | | 失败错误信息原文 | — |
| **error_code** | TEXT | | 失败错误归类码（`OOM_VRAM`/`TASK_TIMEOUT`/`LORA_APPLY`/`WEIGHT_INTEGRITY`/`WORKFLOW_LOAD`/`WATERMARK`/`UNKNOWN`） | **新增（§4.1）**：用于 FAILED 根因聚类 |
| processing_time_s | REAL | | 推理耗时（秒） | 指标口径 |
| output_count | INT | | 成功输出数 | — |
| thumbnail | TEXT | | 缩略图（base64 或路径） | — |
| **workflow_version** | TEXT | | 引擎 workflow 文件内容 sha256（不可变版本指纹） | **新增（§3.3）**：图像→workflow 版本追溯 |
| **lora_checksums** | TEXT(JSON) | | `[{name, strength, sha256}]` 每层 LoRA 权重指纹 | **新增（§3.3）**：图像→权重追溯 |
| created_at | TEXT | | 创建时间（`datetime('now')`） | — |
| updated_at | TEXT | | 更新时间 | — |
| favorite | INT | | 收藏标记（清理时跳过） | 生命周期 |

索引：`idx_tasks_status`、`idx_tasks_engine`、`idx_tasks_created_at`、`idx_tasks_favorite`、`idx_tasks_workflow_version`。

## 表：`outputs`

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER | PK |
| task_id | TEXT | 外键 → tasks.task_id |
| path | TEXT | 输出图像路径（绝对或相对） |
| created_at | TEXT | 创建时间 |

索引：`idx_outputs_task_id`、`idx_outputs_path`。

## 表：`presets`

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER | PK |
| name | TEXT | 预设名 |
| generation_config | TEXT(JSON) | 预设生成参数 |
| created_at | TEXT | 创建时间 |

## 迁移策略

无 Alembic。`HistoryDB._init_db` 在 `CREATE TABLE IF NOT EXISTS` 之后执行
`MIGRATION_SQL`（`ALTER TABLE tasks ADD COLUMN IF NOT EXISTS ...`），保证旧库向前兼容。
新增列必须带 `DEFAULT`，禁止破坏性变更。重大 schema 变更应记录 ADR 并更新本文件。

## 血缘追溯示例

```sql
-- Q1：某张图 → 对应 workflow 版本 + 所有 LoRA 权重指纹
SELECT task_id, workflow_version, lora_checksums, generation_config
FROM tasks WHERE task_id = (SELECT task_id FROM outputs WHERE path = 'outputs/xxx.png');

-- 图像本身仅携带水印 task_id（无 EXIF），DB 为参数唯一事实来源；DB 损坏则血缘断链。
```
