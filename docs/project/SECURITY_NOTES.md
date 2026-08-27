“本文由 2026-08-27 家族治理 E3 从 AGENTS.md §11 移出，内容逐字保留”

# 安全注意事项

1. **PathGuard 路径防护**：所有用户输入参与文件路径拼接（读取 outputs 图片、保存 presets JSON、读取上传图片、读取工作流 JSON）→ 必须过 `PathGuard.resolve(base_dir, user_input)`（`integrated_app/security/path_guard.py`），**禁止 `os.path.join(base, user_input)`**。CI 的 `test_path_guard_attacks.py` 有 30+ 攻击向量，改了相关逻辑必跑。
2. **CSRF 防护**：所有非 GET 请求（POST / PUT / DELETE）必须携带 `X-CSRF-Token` 头。**token 不是从端点获取的**——`middleware/csrf.py` 的 `CSRFMiddleware` 会在每个 GET/HEAD/OPTIONS 响应里下发 `X-CSRF-Token` 响应头 + httponly cookie（`csrf_token`，double-submit 校验），POST 时比对 header 与 cookie。前端 `index.html` 里 fetch 封装已自动处理，**不要在前端代码里绕开它**（旧文档写的 `GET /api/system/csrf-token` 端点不存在）。
3. **Rate Limit 限流三维度**：`middleware/rate_limit.py` 同时限制：① `/api/generate/*` 推理接口（默认 1 次/10s）② `/api/output/*` 上传 / 下载（默认 30 次/分）③ 全局（默认 600 次/分）。真需要压测的话临时调 `config.yaml → server.rate_limit.*`。
4. **完整性校验**：启动时 `integrity_selfcheck.py` 对核心 Python 文件跑 SHA-256，和 `security/integrity_manifest.json` 比对。如果你改了 `app_server.py` / `config.py` / `watermark.py` / `path_guard.py` 等核心文件 → **必须重新生成 manifest**：`python scripts/generate_integrity_manifest.py`，否则下次启动直接退出。
5. **DCT 水印强制嵌入**：所有从 `/api/output/*` 返回的生成图片 **必须** 已嵌入水印（`watermark.py` 的 `embed_dct()`）。不要在任何导出 / 下载路径上跳过水印嵌入，否则溯源能力失效。验证：`python scripts/verify_watermark.py outputs/<image>.png` 能提取出 product_id + task_id。
6. **网络安全**：生产环境 **绝对不能 `config.yaml → server.host = "0.0.0.0"`**，只监听 `127.0.0.1`，外网访问必须套 Nginx（HTTPS + Basic Auth + IP 白名单 + WAF 限频 `/api/generate/*`）。

---
