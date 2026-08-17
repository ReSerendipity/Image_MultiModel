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
- **默认仅绑定 127.0.0.1**：局域网部署请配置反向代理 + Basic Auth
