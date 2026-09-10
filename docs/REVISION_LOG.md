# REVISION_LOG — 桌面分发与安全加固落地记录（2026-09-10）

> 任务：`docs/任务书-桌面分发与安全加固-20260910.md`；执行：MainAgent 全自主；
> 决策台账见《执行对照表》（`docs/reports/执行对照表-桌面分发与安全加固-20260910.md`）。

## 时间线
| 时间 | 事件 |
|---|---|
| 2026-09-10（前段） | P0 完成并提交（commit `06d62da`，tag `p0-signing-enforce-20260910`）：清单签名+enforce+密钥/水印升级 |
| 16:40–17:0x | P1 桌面化：Tauri 壳复制→品牌/标识/密钥适配→cargo check 0 告警 + cargo test 36 passed |
| 17:0x–17:3x | P1-3.1 分层定案；P1-3.3 NSIS（makensis 0 warning）；P1-3.4 分卷（8MB→3 卷闭环 MATCH）；P1-3.5 打包+更新链路；P1-3.6 版本闸门 |
| 17:3x–17:5x | P2：diag_portable_verify（暴露清单过期→重签修复）；release_gate 五步全过；闭源评估文档；阶段2 全量验证（pytest 1018+14 / ruff / mypy / cargo 全绿） |
| 18:0x | 阶段3：config.yaml 恢复、文档同步（README/CHANGELOG/GOTCHAS/SOPS）、分批提交与推送 |

## 提交计划（约定式提交，中文，DCO Signed-off-by）
| 批 | 内容 | 对应报告建议 |
|---|---|---|
| A | desktop/ 壳 + installer + 分层文档 + package_app/split 脚本 + app_server 端口参数 + 版本闸门 + 清单重签 + python_process resolve 修正 | P1-3.1~3.6 |
| B | diag_portable_verify + release_gate + 闭源评估文档 | P2 |
| C | 文档同步（README/CHANGELOG/GOTCHAS/SOPS/REVISION_LOG + 对照表） | 通用收尾 |

## 关键决策摘要（详见对照表决策台账）
1. 版本权威位：保留 config.yaml（用户裁决 d9c997e），任务书"统一 pyproject"以一致性闸门折中。
2. productName=ImageMultiModel（无空格）；更新签名独立密钥对。
3. L2 打包范围=运行时必需+合规文本；壳版本独立演进不参与版本闸门。
4. 双 pytest 并发/系统 python 干扰已清理；门禁统一 .venv。
5. 闭源评估结论：现阶段保持开源（收益有限/可逆）。

## 验证结果
| 项 | 结果 |
|---|---|
| pytest tests | 1018 passed + 14 skipped（= P0 基线） |
| ruff check app tests scripts | 全绿 |
| mypy app/integrated_app | Success（89 文件） |
| cargo check / cargo test（壳） | 0 告警 / 36 passed |
| release_gate 五步 | 全过 |
| 清单门禁 | 33/33 PASS（已重签） |
| diag_portable_verify | ALL_CHECKS_PASS（failed=0，manifest_signed=True，enforce=True） |
| NSIS | makensis 编译 0 warning |
| 分卷 | 切片/校验/拼接还原 MATCH |
