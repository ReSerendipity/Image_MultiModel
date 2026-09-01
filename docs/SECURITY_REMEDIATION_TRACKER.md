# Image MultiModel v2.0.0 — 安全评估整改追踪表

> 配套文档：`docs/_devarchive/SECURITY_ASSESSMENT_v2.0.0.md`（17 项发现 + 三阶段路线图）
> 整改日期：2026-09-01（基于 2026-08-31 评估快照）
> 验证手段：`.venv/Scripts/python.exe -m pytest` 安全测试集 + `scripts/check_config_refs.py` CI 门禁

## 0. 根因修复（最重要的一项）

安全评估结论：**真正的风险不是单点漏洞，而是「配置-实现不一致不报错」**——
`verify_weights: true`、`basic_auth`、`server.ssl` 等声明了却没人读，且不报错、不告警、测试也不失败。

对应评估路线图第三阶段 #13，已落地为 **配置-实现一致性门禁** `scripts/check_config_refs.py`（接入 `.github/workflows/ci.yml:304`）：

- 校验 `config.yaml` 的 `security:` 段每个键都被代码真实消费（声明即生效，否则 CI fail）；
- 校验 `config.yaml` 的 `runtime:` 段每个键都在 `RuntimeConfig` 中定义（防 idle_unload_minutes 式启动阻断回归）；
- 校验代码中访问的 `config.*` 字段都在配置模型中声明。

验证结果：`[PASS] 配置字段引用完整性检查通过（代码访问与 config.yaml 均匹配配置模型）`，security 段 23 个键全部被消费。

## 1. 整改状态总表（17 项）

| ID | OWASP | 问题 | 整改位置 | 状态 | 验收测试 |
|---|---|---|---|---|---|
| **C-01** | A01/A07 | 认证体系零实现 | `middleware/auth.py` + `app_server.py:697` 注册 `AuthMiddleware`；默认 `enabled=false` 保本地零配置 | ✅ 已修 | `test_auth_middleware.py` |
| **H-01** | A02 | HTTPS 死配置 | `app_server.py:795-828` 按 `server.ssl` 构造 uvicorn SSL；缺证书回退 HTTP 并告警 | ✅ 已修 | `test_security_audit.py` |
| **H-02** | A08 | 默认引擎未接入权重校验 | `native/engine.py:92-109` `load()` 逐角色调用 `verify_weight_before_load` | ✅ 已修 | `test_native_security.py` / commit 38b968c |
| **H-03** | A04 | 内容过滤可绕过 | `security/content_filter.py` NFKC 归一化 + 同形字映射 + Prompt Injection 规则集（DAN / `<|im_start|>` 等） | ✅ 已修 | `test_content_filter.py` |
| **H-04** | A08 | 完整性清单漏核心模块 | `_CORE_MODULES` 补 `magic_check/weight_integrity/content_filter`；`test_security_audit.py:166` 升级为 `manifest == set(_CORE_MODULES)` 且 `skipped==0` 断言；清单重算（33 模块） | ✅ 已修 | `test_security_audit.py` |
| **H-05** | A01/A04 | MCP 通道绕过安全链 | `mcp_server.py:448-456` 接入 `filter_image_generation` | ✅ 已修 | `test_mcp_security.py` |
| **M-01** | A01 | `/api/tasks/export` 无 PathGuard | `routes/task_routes.py:69-97` 改用 `PathGuard.resolve(outputs)` 并修复空 ZIP | ✅ 已修 | `test_task_routes_export.py` |
| **M-02** | A05 | 缺安全响应头 | `middleware/security_headers.py`（CSP / nosniff / frame-ancestors）最外层注册 `app_server.py:685` | ✅ 已修 | `test_security_audit.py` |
| **M-03** | A05 | 上传无大小限制 | `routes/preprocess_routes.py:79` 消费 `max_size_mb` + `max_pixels` | ✅ 已修 | `test_generate_routes.py` |
| **M-04** | A08 | `custom_nodes_dir` 注入 sys.path | `native/source.py:54-59` 用 `PathGuard` 校验目录落于项目根内 | ✅ 已修（comfy_kernel vendored 哈希基线为可选加固，未做） | `test_native_kernel_security.py` |
| **M-05** | A06 | 供应链：盲装 pip / 硬编码外部解释器 | `clean_launch.py` 不再盲 `pip install`（改提示），外部解释器改由 `PROJECT_ROOT.glob("WPy64-*")` / 环境变量解析 | ✅ 已修 | `test_clean_launch_security.py` |
| **M-06** | A03 | 前端 3 处 XSS | `app/static/js/app.js:183/420` 改用 `escHtml()`；`r.detail` 走 `alert()` 安全回显 | ✅ 已修 | `tests/frontend/` |
| **M-07** | A05 | `check-image` 可读 `model/` | `config_models.py:359-365` 新增独立 `image_read_base_dirs`；`safety_routes.py:82-84` 优先使用 | ✅ 已修 | `test_security_audit.py` |
| **L-01** | A09 | 完整性自检 `skipped>0` 仍打「通过」 | `integrity_selfcheck.py` 改为 `skipped>0` 显式 WARNING（消除「假通过」） | ✅ 已修 | `test_security_audit.py` |
| **L-02** | A04 | 无密钥时水印未签名可伪造 | 本地优先场景残余风险低；生产部署建议将 `IMAGE_MULTIMODEL_WATERMARK_KEY` 设为启动必需项 | ⚪ 可选（文档建议） | — |
| **L-03** | A05 | 限流 dict key 无回收 / 无代理识别 | `rate_limit.py` 已改模块级存储（commit 3d5139e）；`--proxy-mode` / 可信代理列表未实现（本地 127.0.0.1 部署不触发） | ⚪ 可选（本地部署不触发） | — |
| **L-04** | A05 | 水印鲁棒性弱 | 仅通道 0 前 N 块、无纠错；抗取证强度不足 | ⚪ 可选（声明性溯源已满足） | — |

## 2. 验证结果

```
安全测试集（13 个文件，139 用例）：119 + 20 = 139 passed, 0 failed
CI 门禁 scripts/check_config_refs.py：[PASS]
```

覆盖：C-01 / H-01 / H-02 / H-03 / H-04 / H-05 / M-01 / M-02 / M-03 / M-04 / M-05 / M-06 / M-07 / L-01（全部 Critical/High/Medium + L-01 已落地并验证）。

## 3. 保持绿通的日常纪律

1. **改任何核心安全模块后必须重算清单**：`python scripts/generate_integrity_manifest.py`（否则自检会因哈希失配报 failed，这是预期行为，不是 bug）。
2. **加任何 `config.yaml` 的 `security:` 键必须被代码读取**，否则 CI 门禁 `check_config_refs.py` 直接 fail——这正是根除「配置幻觉」的机制。
3. **新增安全中间件**必须注册进 `app_server.py` 的中间件链并完成接入测试，避免又成「声明未实现」。

## 4. 残余风险说明

- 所有修复均针对「配置-实现不一致」与本地优先（127.0.0.1）部署。若未来**服务化部署**（多人共享 / 反向代理 / 联网 MCP），需补：认证默认开启（C-01）、HTTPS 落地 + HSTS（H-01）、限流代理识别（L-03）。
- L-02/L-03/L-04 为 Low 项，在本地优先形态下残余风险低，标注为可选加固，待服务化时再补。
