# GPL-3.0 合规说明（vendored `comfy_kernel/`）

> 对应 2026-09-04 安全评估 H1：`comfy_kernel/` 由 `.gitignore` 排除（不入 git 仓库），
> 但引擎运行时强依赖它；分发本项目必须履行 GPL-3.0 的「提供对应源码」义务。
> 本文件是最小合规动作的落地文档，配合 `THIRD_PARTY_NOTICES.md` 使用。

## 1. 组件事实

| 项 | 值 |
|---|---|
| 组件 | `comfy_kernel/` — vendored ComfyUI 内核源码 |
| 上游 | <https://github.com/comfyanonymous/ComfyUI> |
| 版本 | ComfyUI 0.32.0（`comfy_kernel/pyproject.toml`） |
| 源码对应提交 | `9883be7c5ec4082a090347d461bb0bd4131516f5`（2026-08-17，含本地内核维护提交） |
| 许可 | GNU GPL-3.0（`comfy_kernel/LICENSE`） |
| 主项目许可 | Apache-2.0（`LICENSE`） |
| 引用方式 | 进程内复用（native 引擎 `comfy_source_dir: comfy_kernel`），非独立进程/网络调用 |

## 2. 「提供对应源码」的两种履行方式（分发者二选一）

**方式 A（推荐）：源码随包分发**
- 便携包（`scripts/pack_portable.ps1`）：STEP 4 人工嵌入 comfy_kernel 时，**必须**将
  完整 `comfy_kernel/` 目录（含 `LICENSE`）复制进分发包——打包脚本该步骤即履行义务；
- Docker 镜像：构建上下文包含 `comfy_kernel/`（确认未被 `.dockerignore` 排除），
  镜像内 `/app/comfy_kernel/` 即源码提供。

**方式 B：书面提供承诺（offline 分发无法附带源码时）**
- 分发包内附本文件与上游地址、提交哈希，承诺自分发之日起三年内、
  收到请求即提供对应源码（GPL-3.0 §6）。
- 注意：本地内核维护提交不在上游仓库中，仅凭上游地址**不构成**「对应源码」，
  必须另行提供（随包附带 diff 或打包源码归档）。

## 3. 分发前自查清单

- [ ] 分发包中存在 `comfy_kernel/LICENSE`（GPL-3.0 全文）
- [ ] 分发包中存在完整 `comfy_kernel/` 源码（方式 A），或已附书面提供承诺（方式 B）
- [ ] `THIRD_PARTY_NOTICES.md` 与 `NOTICE` 中的 comfy_kernel 条目未被删改
- [ ] 主项目 Apache-2.0 与内核 GPL-3.0 的边界未混淆（主仓代码不拷贝内核代码）
- [ ] `pack_portable.ps1` STEP 4 已执行并复核

## 4. 版本升级时的义务

升级 vendored 内核（替换/重放 commit）后，必须同步更新本文件 §1 的
「版本」与「源码对应提交」两行，保证哈希可追溯。
