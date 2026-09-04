# Image_MultiModel · 安全合规评估报告

> 评估日期：2026-09-04 ｜ 评估方法：静态扫描 + 源码实测 + git 追踪面核查 + 配置校验器审查
> 评估对象：`C:/Users/Doro/Image_MultiModel`（项目版本 v1.2.2）
> 威胁模型：**本地回环、单用户自托管的 AI 图像生成服务**。主要风险不是公网入侵，而是「恶意输入/恶意模型文件/恶意网页」借本地服务为跳板读写本机文件，以及开源分发的许可证合规。
> 基线参照：`SECURITY_AUDIT_Image_MultiModel.md`（2026-09-02，评级中）——本报告先读基线、再判增量，不重复其已确认结论。
> 评估框架：`Image_MultiModel_安全合规评估提示词.md`（r2 实测校准）。

---

## 0. 事实核对表（实测值）

| 项 | 提示词锚点（r2 校准后） | 实测结论 | 状态 |
|---|---|---|---|
| host 强制回环 | `config_models.py:36-41` | 校验器 `host_must_be_loopback` 禁止 `0.0.0.0` ✓ | ✅ 一致 |
| CSRF 默认启用 | `config.yaml:181-182` | `csrf.enabled: true` ✓ | ✅ 一致 |
| 限流 | `config.yaml:169-172` | infer 30 / upload 10 / global 600 ✓ | ✅ 一致 |
| 鉴权默认关闭 | `config.yaml:173-180` | basic_auth/api_token 均 disabled ✓ | ✅ 一致 |
| CORS 回环白名单 | `config.yaml:183-188` | 仅 `127.0.0.1:8288`/`localhost:8288`/`ws` ✓ | ✅ 一致 |
| CLIP fail-open | `config.yaml:198-199` | `fail_closed_on_clip_missing: false` ✓ | ✅ 一致 |
| 权重校验块 | `config.yaml:189-194` | `only_safetensors:true`、`verify_weights:true`、`weight_manifest_file:''`、`fail_closed_on_corrupt_weight:false` ✓ | ✅ 一致 |
| 水印配置 | `config.yaml:125-131` | DCT 频域水印、`enabled_in_code:true` ✓ | ✅ 一致 |
| 水印密钥 | `.watermark_key` 66B + `init_watermark_key.py` + `verify_watermark.py` | 存在、被 gitignore、无硬编码 ✓ | ✅ 一致 |
| 路径防护 | `security/path_guard.py` + 23 例测试 | 实测 `resolve()` 已解析符号链接（**反模式 #4 不成立**） | ⚠️ 提示词假设需修正 |
| 完整性 | `integrity_selfcheck` + `weight_integrity.py` | 模块存在且已接线到加载路径（engine/lora/diffusers） | ✅ 一致 |
| 输入校验 | `magic_check.py`/`upload_limits.py` + 测试 | 存在 ✓ | ✅ 一致 |
| mask_sensitive_headers | `config.yaml:241` | `true`（仅 header，body 未核实） | ✅ 一致 |
| NSFW 权重 | `model/unet/Z-image_turbo-bf16/` | `zimageTurboNSFWByStable_2602NSFWFP8.safetensors` 与官方版并存 ✓ | ✅ 一致 |
| 供应链 CI | `security.yml` | pip-audit / CodeQL / Trivy / secret-scan 均存在 ✓ | ✅ 一致 |
| 状态变更端点 | `config_routes.py:54` / `engine_routes.py:205` / `task_routes.py:119` | `/api/config` PUT、/api/engine/unload、/api/tasks/{id}/cancel 均存在 ✓ | ✅ 一致 |
| 内容过滤端点 | 提示词原写 `/api/check-*` | 实测为 `/api/safety/check-prompt`、`/api/safety/check-image`（`safety_routes.py:7-8`） | ⚠️ 提示词路径过时（已修） |
| SECURITY.md | 提示词资产清单列出 | **仓库无此文件** | ⚠️ 提示词路径幻觉（已修，转为评估项） |
| 空 CSP | 提示词视为缺口 | `security_headers.py:90` 代码回退到内置安全默认 CSP（`_DEFAULT_CSP`） | ⚠️ 代码已缓解，非缺口 |
| comfy_kernel 入库 | 提示词称 vendored | `git ls-files comfy_kernel/` = 0 条（`.gitignore:139` 排除） | ⚠️ 与 "vendored 随仓" 口径冲突 |
| history 清理 | `cleanup_cron: "0 3 * * *"` | `app_server.py:422` 在 `keep_days=0 & max_gb=0` 时**直接跳过** → 无限留存 | ⚠️ 隐私缺口确认 |
| uploads TTL 执行者 | `ttl_s: 86400` | grep 未定位 uploads 清理执行者（历史清理已确认，uploads 清理待核实） | ⚠️ 待查 |

---

## 1. 七维度评分（0–5，附证据）

| 维度 | 评分 | 证据与说明 |
|---|---|---|
| 路径与文件安全 | **4.0** | `path_guard.py` 设计扎实：URL 解码、空字节拦截、跨平台盘符归一、`resolve()` 解析符号链接后 `_is_within` 校验、23 例测试。扣分点：全仓 43 端点 vs 仅 3 个路由文件引用 path_guard——需逐端点确认是否过 PathGuard（不能据此断言 40 端点裸奔，但覆盖审计未闭环）。`resolve()` 失败时回退 `p.absolute()`（第 102 行）为理论绕过，记为残差。 |
| 内容安全 | **3.5** | `check_prompt`（关键词+注入规则，含同形字/leetspeak/零宽字符对抗）**无需 CLIP 始终生效**；`check_image`（CLIP）实现完整。核心扣分：`fail_closed_on_clip_missing: false` → CLIP 缺失时图片扫描**静默放行**（prompt 关键词仍拦截，故影响面限于"已绕过关键词的图"）。 |
| 水印与溯源 | **4.0** | DCT 频域水印 `enabled_in_code:true`，密钥 66B 不入库无硬编码，`scripts/verify_watermark.py` 支持 `-p product_id` 校验。扣分：鲁棒性（缩放/压缩/截图抵抗）测试未见；verify 脚本是否进 UI/文档暴露未核实。 |
| 供应链与权重 | **2.5** | 格式白名单 / pickle 探测(CWE-502) / safetensors 头解析**已真实生效**且已接线到加载路径。重大扣分：`fail_closed_on_corrupt_weight:false` → 损坏/被篡改权重**静默跳过该层**（engine.py:124），而非拒绝；`weight_manifest_file:''` → 无预期 hash，**篡改检测缺失**（仅结构校验）。 |
| Web 层防护 | **3.0** | CSRF 启用；`security_headers` 有安全默认 CSP（非配置空串）；认证中间件功能完整（恒定时间比对）。扣分：认证默认全关 + 状态变更端点（`/api/config` PUT 等）默认无保护；回环下 all-requests-same-origin 使限流意义有限。 |
| 开源合规 | **2.0** | 主仓 Apache-2.0，THIRD_PARTY_NOTICES/NOTICE 已登记 comfy_kernel GPL-3.0。**重大扣分**：`comfy_kernel/` 被 gitignore 排除（0 条入库），运行时强依赖它；分发包（release/Docker）若不含其源码即违反 GPL-3.0 提供源码义务；无 `SECURITY.md` 披露渠道；PRIVACY_POLICY 仍称默认 diffusers 引擎（与 native 唯一引擎矛盾）。 |
| 数据留存与隐私 | **2.5** | `mask_sensitive_headers:true`。扣分：`history.cleanup_cron` 在 `keep_days=0` 时**不清理** → 历史库无限留存 prompt/路径（隐私承诺落空）；uploads `ttl_s:86400` 清理执行者未定位；body 脱敏未核实。 |

---

## 2. 风险清单（Critical / High / Medium / Low）

### 🔴 High
- **H1 — GPL-3.0 分发义务未实质履行**（合规/法律）
  - 证据：`git ls-files comfy_kernel/` 返回 0；`.gitignore:139` 排除；引擎运行时强依赖 `comfy_kernel/`（native backend）。THIRD_PARTY_NOTICES:18 亦称其"由 .gitignore 排除"。
  - 影响：若 release/Docker 产物不含 comfy_kernel 源码，分发即违反 GPL-3.0「提供对应源码」义务（即便附 NOTICE 声明也不足以满足"提供源码"）。
  - 命令：`git ls-files comfy_kernel/ | wc -l`；`cat Dockerfile | grep -i comfy`。

- **H2 — 损坏/被篡改权重被静默跳过而非拒绝**（供应链/完整性）
  - 证据：`engine.py:124` `logger.warning(...); 跳过该权重`；`fail_closed_on_corrupt_weight:false`（配置默认）。仅当该开关为 true 才抛 `WeightIntegrityError` 阻断（engine.py:123）。
  - 影响：恶意或被篡改的 `.safetensors` 若结构尚可解析、仅权重被替换，会被静默忽略，攻击者可能借权重加载链路的边界条件影响行为；且用户无感知。
  - 命令：`grep -n "fail_closed_on_corrupt_weight" app/integrated_app/native/*.py`。

### 🟠 Medium
- **M1 — CLIP 缺失时图片内容扫描 fail-open**：`content_filter.py:271-277` 默认放行；`fail_closed_on_clip_missing:false`。prompt 关键词仍拦截，影响限于图面绕过。
- **M2 — 历史库无限留存**：`app_server.py:422` `keep_days=0 & max_gb=0` → cleanup 跳过。prompt/路径长期留存，与隐私承诺不符。
- **M3 — 状态变更端点默认无鉴权**：`/api/config` PUT、`/api/engine/unload`、`/api/tasks/{id}/cancel` 在 `basic_auth`/`api_token` 均关时任意本机进程可调。本地提权面（需本机恶意进程/JS）。
- **M4 — 权重清单为空致篡改检测缺失**：`weight_manifest_file:''`，`validate_weight_file` 仅在 `expected_sha256` 存在时比对 hash（weight_integrity.py:177）；当前只做结构/格式校验，无完整性 hash 比对。

### 🟡 Low
- **L1 — 残留 unsafe-inline CSP**：默认 CSP 保留 `script-src/style-src 'unsafe-inline'`（前端内联事件兼容）。XSS 面被 `escHtml()` 缓解（app.js:183），但非纵深防御。
- **L2 — NSFW 社区权重随产品目录分发**：`zimageTurboNSFWByStable_2602NSFWFP8.safetensors` 与官方版并存，`USER_AGREEMENT` 责任边界未明确点名该文件。
- **L3 — uploads TTL 清理执行者未定位**：`uploads.ttl_s:86400` 存在但 grep 未找到明确清理任务（需进一步核实是否有 APScheduler 作业）。
- **L4 — 缺 SECURITY.md**：无漏洞披露渠道与响应时效约定。
- **L5 — PRIVACY_POLICY 引擎声明过时**：仍称"默认 diffusers 引擎"（PRIVACY_POLICY.md:11,18），实际 native 唯一引擎。
- **L6 — path_guard 解析失败回退**：`path_guard.py:102` `resolve()` 异常时回退 `p.absolute()`（不解析符号链接），理论绕过面（正常路径 resolve 不抛异常，故实际风险低）。

---

## 3. 与基线审计（2026-09-02）的增量差异表

| 基线结论 | 本报告增量 |
|---|---|
| ✓ 无密钥入库 / loopback 强制 / 锁文件齐全 | 维持确认，无变化 |
| ✓ THIRD_PARTY_NOTICES 已声明 comfy_kernel GPL-3.0 义务（"待关注"） | **升级**：确认 comfy_kernel 未入库（0 条），分发义务**实质未满足** → H1（由 Medium 升 High） |
| 待关注 #3：pack_portable.ps1 本地执行无不受控输入 | 维持，未变 |
| （基线未覆盖） | **新增**：H2 权重静默跳过、M1 CLIP fail-open、M2 历史库无限留存、M3 端点无鉴权、M4 清单空转、L2 NSFW 权重、L4 缺 SECURITY.md、L5 隐私政策矛盾、L6 path_guard 回退 |
| （基线未覆盖） | **修正提示词误判**：空 CSP 已由代码默认 CSP 缓解（非缺口）；符号链接已由 `resolve()` 防护（反模式 #4 不成立）；SECURITY.md 实为不存在（提示词幻觉） |

---

## 4. 整改优先级（映射至实施任务 #2–#8）

| 优先级 | 整改项 | 对应风险 | 验收标准 |
|---|---|---|---|
| **P0** | 双 fail-open 默认改 true（CLIP + 权重损坏），含可用性降级策略 | H2, M1 | 配置校验器接受；单测覆盖默认 true 与降级分支；合法 bundled 权重加载不被阻断 |
| **P0** | 权重清单空转 → 生成 bundled 官方权重 manifest + 加载路径接入 hash 比对 | H2, M4 | bundled 权重登记 hash；篡改(hash 不符)被拒绝；用户自添权重有 documented 路径 |
| **P1** | 引入最小默认鉴权（首启生成 api_token 并启用，保护状态变更端点） | M3 | 回环调用带 token 通过、无 token 返回 401；本地零配置体验可选保留(off-by-default 安全增强) |
| **P1** | GPL-3.0 分发义务：release/Docker 含 comfy_kernel 源码或书面提供方式 + COMPLIANCE-README | H1 | 分发包含源码或提供方式文档；CI 不依赖未登记项 |
| **P1** | 符号链接耗时残留（L6）+ 路径防护逐端点覆盖审计闭环 | L6, 路径维度扣分 | path_guard 解析失败不再回退裸 absolute；覆盖审计完成 |
| **P2** | 历史库清理语义修正（keep_days=0 含义明确 / 可选默认 90 天） | M2 | 清理任务按预期运行；留存期可配置且有默认 |
| **P2** | uploads TTL 清理执行者核实/补 | L3 | 清理任务存在并运行（APScheduler） |
| **P2** | 文档：PRIVACY_POLICY 引擎声明修正、增补 SECURITY.md、NSFW 权重责任边界 | L4, L5, L2 | 文档一致；SECURITY.md 含披露渠道 |
| **P2** | XSS 纵深：消除 unsafe-inline（前端事件委托）或确认 escHtml 全覆盖 | L1 | 无内联脚本 CSP 可用；动态注入均经 escHtml |

---

## 5. 必答三问答复

**Q1：两处 fail-open 是否应改 true？若改，模型/权重缺失时可用性如何保障？**
→ 建议**改 true**。CLIP 缺失时分级降级：**默认 fail-closed（拦截图片扫描）**，但提供运行时开关（已在 `content_filter.py:160` `set_fail_closed_on_clip_missing`）允许运维在高温/无 GPU 场景临时 fail-open，并强制记录 `degraded` 审计日志 + UI 横幅提示。权重损坏 fail-closed 对合法 bundled 权重零风险（均为合法 safetensors），用户自添损坏权重会被拒绝并给出明确错误，符合"不静默跳过"原则。

**Q2：回环+鉴权默认关，是否值得引入最小鉴权？**
→ **值得，但默认仍 off、提供安全增强开关**。实现首启自动生成 `api_token` 写入本地配置并可选启用，保护 `/api/config` PUT、/api/engine/unload、/api/tasks/{id}/cancel。`auth.py` 已完整实现，仅需 bootstrap 接线；代价是本地脚本/前端需带 token，收益是本机恶意进程无法静默改配置/卸载引擎。回环零配置体验通过"不默认开启"保留。

**Q3：vendored GPL-3.0 分发义务当前是否履行？若未履行，最小合规动作？**
→ **当前未实质履行**（comfy_kernel 未入库）。最小动作：① 在 release/Docker 构建中把 `comfy_kernel/` 一并打包（源码随附，最直接）；或 ② 随包附 `COMPLIANCE-README.md` 写明对应源码获取方式（上游仓库 + 本仓锁定 commit）；③ `THIRD_PARTY_NOTICES.md` 补充"分发形态与源码获取方式"段落；④ CI 增加校验：若 `comfy_kernel/` 缺失则 release 产物构建失败。属合规动作，最终分发形态需用户拍板。

---

*本报告为静态/半静态评估，未做动态渗透；评分与风险等级按本地自托管工具威胁模型设定，未按公网服务虚增。*

---

## 6. 整改执行记录（2026-09-04 同日落地）

| 风险 | 整改动作 | 关键文件 | 验证 |
|---|---|---|---|
| H2 | `fail_closed_on_corrupt_weight` 默认改 true（配置+代码双对齐），损坏权重拒绝加载而非静默跳过 | `config.yaml`、`config_models.py:323` | 新增发行配置守护测试；41 tests |
| M1 | `fail_closed_on_clip_missing` 配置改 true（代码默认本已安全），CLIP 不可用时明确记录策略决策审计日志 | `config.yaml`、`content_filter.py` | test_content_filter 全过 |
| M4 | 激活权重完整性清单：共享助手 `resolve_expected_sha256` 接入 engine/diffusers/lora 三链路；`manifest_hash_for_path` 补符号链接逻辑键回退；TOFU 清单生成（51 权重）+ `allow_unregistered_weights` 策略 | `weight_integrity.py`、`engine.py`、`lora.py`、`diffusers_engine.py`、`scripts/generate_weight_manifest.py`、`config.yaml` | 端到端验证默认引擎 3 角色 registered=True；18 tests |
| 🆕生产缺陷 | **本机生成中断修复**：`pretrained_models/` 缺失导致 09-03 起 FileNotFoundError（日志实证）；按 pack_portable/install.bat/compose 三方一致的正统目录，以 junction 恢复 `pretrained_models/{text_encoders,unet,vae,loras}` | junction ×4、`.gitignore` | 引擎权重文件可达；清单键命中 |
| M3 | 最小鉴权 bootstrap（off-by-default）：`security.api_token.bootstrap: true` 时首启生成 token 至 `.api_token` 并启用鉴权 | `auth_bootstrap.py`、`app_server.py`、`config_models.py` | 5 新增单测 + 既有 auth 中间件测试 |
| 路径 | `resolve()` 失败 fail-closed（不再回退未解析 absolute）；逐端点覆盖审计闭环（governance/engine 的 path 均为服务端数据） | `path_guard.py` | 35 tests（含 junction 环双平台用例） |
| H1 | GPL 最小合规：`docs/GPL_COMPLIANCE.md`（源码获取方式+版本锁定 0.32.0/`9883be7c`+分发自查清单）、THIRD_PARTY_NOTICES 回链、CI license-notice-check 门禁、pack 脚本 STEP 4 合规指引 | `docs/GPL_COMPLIANCE.md` 等 | YAML 校验通过；spec 引用审计 0 幻影 |
| L1 | XSS 审计闭环：修复预设名（`p.name`）与输出文件名 2 处未转义注入；FONTS 为静态数组；unsafe-inline 移除列为前端事件委托重构的前置任务 | `static/js/app.js` | node xss_regression 11/11 |
| L2/L4/L5 | PRIVACY_POLICY 引擎声明修正；新增 SECURITY.md（披露渠道+响应时效）；USER_AGREEMENT 增补 §6 权重责任边界 | 3 份文档 | spec 引用审计通过 |
| L3 | uploads TTL 清理接线（模块此前存在但零调用点）：无条件随日维护 cron 联跑 | `app_server.py` | 代码路径审查 |

**残余（记录在案，不属本轮范围）**：CSP `unsafe-inline` 需前端事件委托重构后收紧；`keep_days=0` 语义（=不清理）为用户显式选择，已由快照+清理解耦机制保障可随时开启；`scripts/git-hooks` 幻影引用已顺手修复。
