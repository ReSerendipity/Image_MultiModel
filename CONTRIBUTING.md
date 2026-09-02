# Contributing to Image MultiModel

Thank you for your interest in contributing to Image MultiModel — a multi-engine image generation platform (Z-Image-Turbo diffusers 为主，兼容 ComfyUI 工作流)。

This document gives a short "10-minute quick start" to get contributors productive, and a concise reference for common contribution tasks.

---

## Quick Start (10 minutes)

1. Clone the repository

```bash
git clone https://github.com/ReSerendipity/Image_MultiModel.git
cd Image_MultiModel
```

2. Run with Docker (one-line start)

```bash
docker compose up --build -d
# Or use provided script (Windows)
start.bat
```

3. Create a branch for your change

```bash
git checkout -b fix/short-description
# make changes, run tests, then push
git commit -m "fix(engine): short description"
git push origin fix/short-description
```

4. Open a Pull Request using the provided template.

---

## Development (local)

Prerequisites
- Python 3.10+ (3.12 recommended)
- NVIDIA GPU (CUDA 13.2) 用于模型推理测试
- Git

Install (dev)

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -e ".[dev]"
```

Run tests

```bash
pytest tests/ -v -m "not e2e"
```

Lint/format

```bash
ruff check app/integrated_app/ scripts/
ruff format app/integrated_app/ scripts/
```

---

## How to File Good Issues

- Bug reports: include environment (OS, Python, GPU, CUDA), steps to reproduce, expected vs actual behavior, and logs (logs/app.log).
- Feature requests: describe the use case, proposed solution, and any alternatives.

Use the provided issue templates (bug_report / feature_request).

---

## Pull Request Checklist

- Use a descriptive title and include a short summary in the PR body.
- Link related issues using `Closes #<issue>` when appropriate.
- Add tests for new behavior where feasible.
- Run tests & linters locally before opening the PR.
- Follow Conventional Commits for commit messages (`feat:`, `fix:`, `docs:`, etc.).

---

## 提交前必做（本地门禁）

> 目标：让每一次提交都能顺利通过 CI，而不是反复修。

### 安装 git hooks（一次即可）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-hooks.ps1
```

之后每次 git push 前自动跑**快检**（ruff / 格式 / compileall 语法 / UTF-8 编码扫描），不过会阻止推送。也可手动：

```bash
python scripts/check_local.py          # 快检（秒级）
python scripts/check_local.py --full   # 快检 + 全量 pytest
```

> CI 是唯一权威门禁。git push --no-verify 可绕过（不推荐）。

### 编码卫生

- 所有源码/文本文件必须为 UTF-8 无 BOM（.gitattributes 已统一 LF 行尾）
- 禁止用第三方编码转换工具批量改写源文件后直接提交（曾导致中文乱码 SyntaxError）
- 本地检查会自动扫描全部被跟踪文本文件的 UTF-8 合法性

### 新增依赖

- 运行依赖 → requirements.txt；测试/开发依赖 → requirements-dev.txt
- 不要只 pip install 后就不管：CI 从干净环境只装 requirements，漏写必红
- 锁文件变更走 requirements-lock.txt（pip-compile 生成）

### 覆盖率门槛

- 只在 CI 判定（跨平台数值有差异，本地不判）；CI 红在覆盖率时补测试而不是调门槛
- 家族约定：阈值不高于 40%，防止贡献者被门槛劝退

### CI 红了先看什么

| 现象 | 常见根因 | 处理 |
|---|---------|------|
| cancelled | 连续 push 取消旧 run | **不是失败**，看最新 run |
| ruff/black 红 | 没跑本地门禁 | python scripts/check_local.py 修复后重推 |
| mypy 红 | 类型错误 | 本地 python -m mypy app/integrated_app 先修 |
| pytest 红 | 测试失败/缺依赖 | 本地 --full 复现；缺依赖补 requirements |
| 覆盖率红 | 新代码没测 | 补测试 |
| SyntaxError/乱码 | 编码损坏 | 本地 UTF-8 扫描定位修复 |

---

## License

By contributing, you agree your contributions are licensed under the Apache License 2.0 (see [LICENSE](LICENSE)).

## DCO (Developer Certificate of Origin)

This project requires all contributors to sign their commits with the Developer Certificate of Origin (DCO).

```bash
git commit -s -m "feat(engine): add streaming generation support"
```

PRs will be checked for DCO compliance. Commits without a `Signed-off-by` line will be rejected.

---

Thank you for contributing — the community makes this project better!