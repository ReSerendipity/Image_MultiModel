# Runbook: 磁盘满 / 输出与数据库异常（告警 `DiskSpaceLow`）

> 关联告警：`DiskSpaceLow`（critical，磁盘可用空间 <15%）
> 关联范围：磁盘容量、输出目录 `outputs/`、历史数据库 `data/history.db`
> 评估 §9-P1-6 第 4 类：数据库 / 磁盘 / 输出目录异常

## 1. 症状（Symptom）
- `/api/alerts` 出现 `DiskSpaceLow` 且 `firing=true`。
- 生成任务落盘失败（写 `outputs/` 报 No space / PermissionError）。
- history DB 写入异常、SQLite `database or disk is full`。
- 启动或清理任务报 IO 错误。

## 2. 确认命令（Confirm）
```bash
# 磁盘可用
df -h .            # Linux
# Windows: wsl df 或资源管理器
curl -s http://127.0.0.1:8288/api/metrics/prometheus | grep "disk_free_bytes"

# 输出目录体积
du -sh outputs data 2>/dev/null

# history DB 完整性
python - <<'PY'
import sqlite3
c = sqlite3.connect("data/history.db")
print(c.execute("PRAGMA integrity_check").fetchone())
PY

# 孤儿/重复输出检测（见 P2-13 备份治理）
python scripts/backup_state.py --check
```

## 3. 影响判断（Impact）
- 磁盘满会直接阻断新图落盘，生成任务失败但不影响已存在数据。
- history DB 损坏会丢失生成记录 / 续跑能力，需从备份恢复。
- 输出目录与 DB 不一致（孤儿输出 / 缺记录）会影响审计与下载。

## 4. 临时缓解（Mitigate）
1. 立即清理：运行历史清理 cron（配置 `keep_days` / `max_gb`），或手动删除最旧 `outputs/` 子目录。
2. 释放空间后确认 `disk_free_bytes` 回升到 >15%。
3. 若 DB 写满但可恢复，先备份再 `VACUUM`：
   ```bash
   cp data/history.db data/history.db.bak-$(date +%s)
   sqlite3 data/history.db "VACUUM;"
   ```

## 5. 回滚 / 重启（Rollback / Restart）
- 磁盘问题无需重启；清理后自动恢复。
- 若 DB 损坏需从备份恢复：
  ```bash
  cp data/history.db.bak-<ts> data/history.db
  ```
- 恢复后重启服务以重建连接池。

## 6. 数据保护（Data Protection）
- **删除 outputs 前先备份**：`cp -r outputs outputs.bak-$(date +%s)`。
- 备份 history DB（见 P2-13）：`python scripts/backup_state.py --backup`。
- 禁止直接 `rm -rf outputs` / `data`；优先用项目内清理机制。

## 7. 恢复验证（Verify）
- `DiskSpaceLow` 在 `/api/alerts` 中 resolved，`disk_free_bytes` > 15%。
- 提交生成任务成功落盘（outputs 出现新文件）。
- `sqlite3 data/history.db "PRAGMA integrity_check"` 返回 `ok`。
- 孤儿检测无异常（`scripts/backup_state.py --check` 通过）。

## 8. 升级联系人（Escalation）
- P2：值班清理并监控。
- P1：DB 损坏或无法恢复，升级到服务 Owner + DBA。
- 事后复盘容量规划（P1-9）与备份频率（P2-13）。
