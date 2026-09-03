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
- NVIDIA GPU (CUDA) for model inference
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

## License

By contributing, you agree your contributions are licensed under the Apache License 2.0 (see [LICENSE](../LICENSE)).

## DCO (Developer Certificate of Origin)

This project requires all contributors to sign their commits with the Developer Certificate of Origin (DCO).

```bash
git commit -s -m "feat(engine): add streaming generation support"
```

PRs will be checked for DCO compliance. Commits without a `Signed-off-by` line will be rejected.

---

Thank you for contributing — the community makes this project better!
