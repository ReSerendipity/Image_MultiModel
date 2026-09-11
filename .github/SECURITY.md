# 安全政策 (Security Policy)

## 支持的版本

| 版本 | 支持状态 |
|------|----------|
| 2.x（main 分支） | ✅ 积极维护 |
| 1.x | ❌ 不再维护 |

## 报告安全漏洞

请**不要**在 GitHub Issues 中公开披露安全漏洞。请通过以下任一方式私下报告：

- 邮件：ReSerendipity@outlook.com（标题注明 `[SECURITY]`）
- 或直接创建 [Private vulnerability report](https://github.com/ReSerendipity/Image_MultiModel/security/advisories/new)

## 响应时间

- 确认收到报告：48 小时内
- 初步评估与修复计划：5 个工作日内
- 严重（Critical/High）漏洞：优先修复并尽快发布补丁

## 安全设计（本项目内置防护）

- **PathGuard**：路径穿越防护，所有文件 I/O 限制在白名单目录
- **CSRF 中间件**：表单 / POST 路由统一 Token 校验
- **Rate Limit**：API 限流防滥用
- **完整性自检**：关键安全模块 SHA256 校验（integrity_manifest.json）
- **DCT 数字水印**：输出图像嵌入可溯源水印（product_id / task_id / timestamp）
- **默认仅绑定 127.0.0.1**：局域网部署请配置反向代理 + Basic Auth

## 补充内置机制（自原根 SECURITY.md 合并，2026-09-11 自净化整改）

- 权重加载前完整性校验（格式白名单 / pickle 探测 / SHA256 清单比对）
- CLIP 内容过滤 + prompt 关键词/注入规则
- 可选鉴权：HTTP Basic / Bearer Token（`security.api_token.bootstrap` 支持首启自动启用）
- 依赖审计：pip-audit / CodeQL / Trivy（`.github/workflows/security.yml`）

## 威胁模型范围与除外条款

本项目威胁模型为**本地回环、单用户自托管**服务（`server.host` 强制 127.0.0.1，见 `config_models.py`）。以下**不属于**漏洞范畴：需要修改本机配置（关闭回环强制）才能触发的暴露、本地物理访问、以及对用户自行替换模型权重/自建引擎引入的风险。

评估基线与完整发现见 `docs/security_compliance_assessment_2026-09-04.md`（本地文档，未随仓库发布）。

> 原根目录 `SECURITY.md` 副本已移除，本文件为唯一事实来源；响应时效以本文件为准（确认收到 48 小时内）。
