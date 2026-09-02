# 安全审计 — Image_MultiModel

> 只读审计 · 快照版 · 审计日期：2026-09-02
> 审计对象：FastAPI + 图像生成平台（默认引擎 `z_image_turbo_native`，backend: native，进程内复用 vendored `comfy_kernel/`）
> 方法：静态扫描 + git 追踪面核查 + 配置校验器审查。未做动态渗透。

## 执行摘要（总体评级：中 / Medium）

无凭据入库、依赖锁定齐全、host 强制回环校验器为审计前已内置（先于本次审计）。主要暴露面集中在**默认 native 引擎复用的 vendored ComfyUI 内核（GPL-3.0）** 与 **对外服务需显式配置认证**。已确认项见下，未发现硬编码密钥或命令注入。

## 已验证项（✓ = 本次核查通过）

### 1. 凭据 / 密钥
- **✓ 无密钥入库**：`git ls-files` 扫描 `.env`、`*.jks`、`*.keystore`、`*.pem`、`*.key`、`secrets/` 均无命中；仅存在 `scripts/init_watermark_key.py`（密钥初始化脚本，密钥本体不入库）。
- **✓ 水印密钥无默认值**：`app/integrated_app/watermark.py` 密钥仅取自环境变量或 `.watermark_key` 文件，无硬编码默认值。
- **✓ .gitignore 覆盖**：`.env`、`.watermark_key`、密钥/凭据类路径均已忽略。

### 2. 网络暴露 / 绑定
- **✓ loopback 强制**：`app/integrated_app/config_models.py:37` 内置 host 校验器，禁止将 host 改为 `0.0.0.0`；全量 grep 非测试代码无 `0.0.0.0` 绑定。

### 3. 依赖供应链
- **✓ 锁文件齐全**：`requirements-lock.txt`（pip-compile 全量 pin）。

### 4. 第三方组件
- **✓ 声明完整**：`THIRD_PARTY_NOTICES.md` 已列明默认引擎 `z_image_turbo_native` 复用 ComfyUI 内核（GPL-3.0）义务与 Z-Image-Turbo 模型（Apache-2.0）。

## 待关注点位（非阻断）

| # | 级别 | 点位 | 建议 |
|---|---|---|---|
| 1 | Medium | 默认引擎 `z_image_turbo_native` 进程内复用 GPL-3.0 的 `comfy_kernel/` | 分发时遵守 GPL 义务并附 `comfy_kernel/COMPLIANCE-README.md`；`comfy_kernel/` 由 `.gitignore` 排除不入库 |
| 2 | Low | Docker/容器场景若前端转发公开端口 | 部署时用 `docker-compose.yml` 端口映射 + 反向代理认证，不直接暴露后端 |
| 3 | Info | `scripts/` 内 PowerShell 打包脚本（pack_portable.ps1）涉及文件系统操作 | 仅本地执行，无不受控输入面 |

## 门禁适用性说明

本仓库 `scripts/check_config_refs.py` 已覆盖 config.yaml 的 `security:` 段键消费校验；`check_spec_refs.py` 已覆盖规范文件引用一致性——本审计与其互不替代。

---

*快照审计，非正式安全承诺；建议在每次大版本发布前复核。*