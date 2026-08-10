<!--
感谢你提交 Pull Request！请完成以下自查清单后再提交。
-->

## PR 摘要

<!-- 用 1-2 句话描述这个 PR 做了什么 -->

## 变更类型

- [ ] feat: 新功能
- [ ] fix: Bug 修复
- [ ] docs: 文档变更
- [ ] test: 测试相关
- [ ] refactor: 重构
- [ ] perf: 性能优化
- [ ] security: 安全修复
- [ ] chore: 构建/工具/依赖

## 自查清单

### 代码质量

- [ ] 代码通过 `ruff check bin tests`（0 error）
- [ ] 代码通过 `ruff format bin tests`（格式化）
- [ ] 类型标注完整（核心模块）
- [ ] 无 `# TODO` / `# FIXME` 残留（或已记录到 Issue）

### 测试

- [ ] 新增/修改的功能已补充 `test_` 测试
- [ ] `python -m pytest -q` 全量测试通过（0 failed）
- [ ] 覆盖率不低于 75%（`python -m pytest --cov=bin/integrated_app`）
- [ ] 安全相关功能已补攻击测试（PathGuard / SQL 注入等）

### 文档与计划

- [ ] `CHANGELOG.md` 已更新（在对应版本下追加条目）
- [ ] `MASTER_PLAN.md` 对应里程碑已更新（如适用）
- [ ] 新增 API 端点已更新 `docs/API.md` 和 `examples/`（如适用）
- [ ] README.md 已更新（如涉及新功能/安装步骤变更）

### 安全

- [ ] 文件路径操作经过 `PathGuard` 校验（无路径穿越风险）
- [ ] SQL 查询使用参数化（无注入风险）
- [ ] 用户输入经过校验（Pydantic Model 或显式校验）
- [ ] 无敏感信息泄露（密码/Token/路径等不在日志中明文输出）

### 兼容性

- [ ] `config.yaml` 新增字段有合理默认值（不破坏现有配置）
- [ ] 不影响已有 API 端点的响应格式（或已做向后兼容）
- [ ] 前端 `static/index.html` 变更不影响已有功能

## 关联 Issue

<!-- 如果这个 PR 解决了某个 Issue，请在这里引用 -->
<!-- 例如: Closes #123, Fixes #456 -->

## 测试结果

<!-- 粘贴 `python -m pytest -q` 的输出摘要 -->
```
287 passed, 0 failed, 0 warnings
```

## 补充说明

<!-- 还有其他需要 reviewer 注意的事项吗？ -->
