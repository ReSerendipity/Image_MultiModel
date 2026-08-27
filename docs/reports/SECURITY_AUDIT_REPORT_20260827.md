# Image_MultiModel 安全状况评估报告

> ⚠️ 本报告位于 `docs/reports/`（本地文档，未随仓库发布）。
> 日期：2026-08-27 · 基于家族规范治理 Phase C/D 实施后实测。

## 一、执行摘要

本仓核心安全关注点在于内嵌 ComfyUI 内核（`comfy_kernel/`，GPL-3.0）与默认 native 引擎的演进。本次治理完成：许可证台账建立、ComfyUI 内核（native 引擎）状态诚实化（deprecated 标记）、禁区目录声明、文档链接真实性标注。总体风险「中」，主要剩余为 GPL 传染与分发形态决策（需人工）。

## 二、归属权篡改风险评估

- 提交链路：`main` + release-please；`.github/workflows` 6 个（ci / docs-consistency / pages-deploy / release / release-please / security）。
- 完整性：`scripts/generate_integrity_manifest.py` 提供完整性清单能力。
- 本次补强：ISSUE_TEMPLATE（bug_report）与 CODE_OF_CONDUCT 补齐。

## 三、安全风险评估

| 攻击面 | 现状 | 状态 |
|---|---|---|
| GPL-3.0 内核传染 | `comfy_kernel/` 仅旧版 native 引擎进程内复用时加载（已 deprecated）；默认 diffusers 引擎不加载 | 已核对（风险待分发决策） |
| 上传/路径穿越 | outputs 读写须过 PathGuard + base_dir（AGENTS.md 硬约束 #5） | 已核对 |
| 网络暴露面 | 默认 127.0.0.1；对外需鉴权 | 待办 |
| 文档幻影 | 审计器 0 幻影 0 死链 | 已核实 |

## 四、技术风险评估

- native 引擎 deprecated 与 M1「ComfyUI 适配（计划，未实现）」已诚实标注（ADR-0001 记录）。
- `docs/` 未入库（57 个文件本仓视角）→ 文档仅本机可读，已按 C0 决策标注链接。

## 五、风险汇总矩阵

| 编号 | 风险 | 可能性 | 影响 | 综合 | 状态 |
|---|---|---|---|---|---|
| R-01 | comfy_kernel GPL 传染 | 中（仅启用 native 时） | 高 | 中 | 已评估，分发决策待人工 |
| R-02 | ComfyUI 适配伪现状 | 已消除 | 低 | 已修复 | 已修复（M1 标「计划未实现」） |
| R-03 | 文档链接指向未入库文件 | 已消除 | 低 | 已修复 | 已修复（C0 标注） |
| R-04 | 公网暴露 | 低 | 高 | 中 | 待办 |

## 六、已落地修复项（本次实施）

- 许可证台账：`docs/LICENSE_COMPLIANCE.md`（comfy_kernel GPL-3.0 矩阵 + custom_nodes 现状「无第三方包」+ 引用 THIRD_PARTY_NOTICES.md）。
- ADR：`docs/adr/0001-native-engine-comfy-kernel.md`、`0002-docs-reorganization-20260823.md`。
- 禁区目录章节（model/、comfy_kernel/、outputs/、docs/_devarchive/）。
- 治理文件：`.github/ISSUE_TEMPLATE/bug_report.md`、`.github/CODE_OF_CONDUCT.md`。
- 链接标注：README 2 处 + AGENTS.md 1 处「本地文档，未随仓库发布」。

## 七、修复验证记录

```powershell
python scripts/check_spec_refs.py          # phantom=0 dead_links=0 → 退出码 0
python C:\Users\Doro\.spec_audit\audit_spec_refs.py   # [high-confidence findings] 0
```

## 八、中长期修复路线图

| 优先级 | 事项 | 状态 |
|---|---|---|
| P1 | comfy_kernel 分发形态人工决策（隔离 or 移除 native 路径） | 待办（需人工） |
| P1 | 对外部署鉴权与 HTTPS | 待办 |
| P2 | native 引擎下线清理节奏 | 待办 |

## 九、结论与建议

GPL 传染是唯一需要人工拍板的关键决策项；其余风险已通过文档诚实化与审计器回归管住。建议在移除 native 引擎前不对外分发便携包。