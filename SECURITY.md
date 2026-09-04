# 安全策略（Security Policy）

## 支持版本

| 版本 | 支持 |
|---|---|
| 最新 release | ✅ |
| 旧版本 | ❌（请升级后复测） |

## 如何报告漏洞

- **请勿**在公开 Issues / Discussions 中披露可利用细节。
- 通过 GitHub **Private vulnerability reporting**（仓库 Security 标签页 → Report a vulnerability）私下报告；或联系仓库维护者。
- 报告请包含：影响版本、复现步骤/POC、影响评估、可能的修复建议。

## 响应时效（尽力承诺）

| 阶段 | 目标 |
|---|---|
| 确认收到 | 72 小时内 |
| 初步评估与分级 | 7 天内 |
| 修复或缓解发布 | Critical 30 天内 / High 90 天内 |

## 范围说明

本项目威胁模型为**本地回环、单用户自托管**服务（`server.host` 强制 127.0.0.1，见 `config_models.py`）。以下不属于漏洞范畴：需要修改本机配置（关闭回环强制）才能触发的暴露、本地物理访问、以及对用户自行替换模型权重/自建引擎引入的风险。

## 已知安全机制

- 路径穿越防护（`security/path_guard.py`）与 14 类攻击回归测试
- 权重加载前完整性校验（格式白名单 / pickle 探测 / SHA256 清单比对）
- CLIP 内容过滤 + prompt 关键词/注入规则
- CSRF、限流、安全响应头（`middleware/`）
- 可选鉴权：HTTP Basic / Bearer Token（`security.api_token.bootstrap` 支持首启自动启用）
- 依赖审计：pip-audit / CodeQL / Trivy（`.github/workflows/security.yml`）

评估基线与完整发现见 `docs/security_compliance_assessment_2026-09-04.md`。
