# 状态与备份治理（P2-13）

> 评估依据：`OPS_STABILITY_ASSESSMENT_v2.0.0.md` §9-P2-13
> 脚本：`scripts/backup_state.py`（子命令 backup / verify / orphans / restore-drill）
> 测试：`tests/release/test_backup_state.py`（11 项）

## 1. 备份（backup）

```bash
python scripts/backup_state.py backup            # → backups/imm_state_<UTC时间戳>.tar.gz
```

- 使用 **SQLite Online Backup API**（`src.backup(dst)`）做一致性快照——直接复制
  `history.db` 文件在 WAL 模式下可能拿到撕裂页，backup API 会合并 WAL 后输出单文件；
- 快照生成后**立刻** `PRAGMA integrity_check`，坏备份直接报错退出；
- 包内同时携带 `config.yaml`、`data/checkpoints/` 清单与 `backup_manifest.json`
  （行数指纹 + config sha256 + 完整性结果），备份自证健康；
- 产物目录 `backups/` 不入库，运维侧应再同步到异机/对象存储（3-2-1 原则）。

## 2. 校验（verify）

```bash
python scripts/backup_state.py verify                      # 在线 DB 巡检（cron 每日）
python scripts/backup_state.py verify --file backups/imm_state_xxx.tar.gz   # 备份包校验
```

备份包校验 = 解包 → integrity_check → 行数与 manifest 比对（行数漂移说明备份被篡改/截断）。
失败退出码 1，可直接接 cron 报警或 `QueueOverload` 同类告警通道。

## 3. 孤儿检测（orphans）

三方一致性：

| 类别 | 含义 | 处置 |
|---|---|---|
| `missing_files` | DB outputs 记录 → 磁盘文件不存在 | `--prune-db --yes` 删除记录（**自动先整库备份**） |
| `unindexed_files` | outputs/ 磁盘图片 → 无 DB 记录 | 仅报告；人工确认后再处理（可能是下载未入库或手动拷入） |
| `orphan_rows` | outputs.task_id 不在 tasks 表 | 同 missing_files 一并可清 |

```bash
python scripts/backup_state.py orphans --report /tmp/orphans.json          # 只报告
python scripts/backup_state.py orphans --prune-db --yes                    # 清理 DB 记录
```

**当前库实测**（2026-09-01）：982 条 outputs 记录中 135 条缺文件（多为 FakeEngine 测试的
系统临时目录产物，环境重启即消失）、8 个未入库文件、0 条孤儿 task 引用。
首次上线后建议跑一次 `--prune-db --yes`，之后每周 cron `orphans` 报告即可。

## 4. 恢复演练（restore-drill）

```bash
python scripts/backup_state.py restore-drill
```

备份 → 解包还原到隔离目录 → integrity_check → 行数比对 → 模拟重启后查询链路
（completed tasks / presets 可查询）。任何一步失败退出码 1。
建议：**每次 schema 迁移后 + 每月至少一次** 跑演练，并把输出归档到发布记录（联动 P2-14）。

## 5. Schema migration 兼容性约定

`history_db.py:_apply_migrations` 采用 **加法迁移**（`ALTER TABLE ... ADD COLUMN`，
列已存在时静默跳过）：

- **向前兼容（旧库 → 新代码）**：新代码启动时自动补列，旧库直接升级，无需停服迁移；
- **向后兼容（新库 → 旧代码）**：旧代码 `SELECT` 显式列名不受新增列影响；
  ⚠️ 但 `SELECT *` + 按位置取值的代码不兼容——新增列必须加在表尾且迁移前 grep 确认无按位置消费；
- **禁止**在自动迁移中删列/改类型（不可逆）；确需破坏性变更时走独立迁移脚本 +
  先 `backup` → 迁移 → `verify` → `restore-drill`，失败则按 `docs/runbooks/service_startup.md` 回滚。
- `schema_fingerprint()` 可导出版本指纹（user_version + 表 DDL），发布前后比对以证明迁移生效。

## 6. 回滚后一致性检查（联动 P2-12）

blue-green `rollback` 只回滚**代码镜像**；数据（DB/outputs/checkpoints）不回滚。
因此回滚完成后必须跑：

```bash
python scripts/backup_state.py verify            # DB 健康
python scripts/backup_state.py orphans           # 新版本写入的数据在旧版本代码下仍可查询
```

旧版本代码遇到新版本新增列时，只要遵守上面「加法迁移」约定就不会破坏
（新列有默认值，旧代码不读）。若 orphans 报告出现异常增量，按事故处理（P2-14 流程）。

## 7. 定时任务建议（部署机 cron 示例）

```cron
0 3 * * * cd /opt/imm && python scripts/backup_state.py backup >> logs/backup.log 2>&1 && find backups -name '*.tar.gz' -mtime +14 -delete
30 3 * * * cd /opt/imm && python scripts/backup_state.py verify --file $(ls -t backups/*.tar.gz | head -1) || echo "BACKUP VERIFY FAILED" | tee -a logs/backup.log
0 4 * * 0 cd /opt/imm && python scripts/backup_state.py orphans --report logs/orphans_weekly.json
0 5 1 * * cd /opt/imm && python scripts/backup_state.py restore-drill >> logs/drill.log 2>&1
```

## 8. 验收对照（§9-P2-13）

- [x] history DB 定期备份（SQLite backup API + 完整性自检 + cron 模板）；
- [x] 完整性校验（verify 在线/离线两模式，损坏可检出——有测试）；
- [x] 恢复演练（restore-drill 端到端，实测通过：833 completed tasks 可查询）；
- [x] schema migration 向前/向后兼容约定（§5，加法迁移 + 表尾新增 + 禁止破坏性变更）；
- [x] 回滚后一致性检查流程（§6，与 bluegreen rollback 联动）；
- [x] 输出文件与 DB 记录孤儿检测（三类检测 + 安全清理 + 已对真实库跑通）。
