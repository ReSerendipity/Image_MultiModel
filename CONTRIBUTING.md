# 参与贡献 (Contributing to Image MultiModel)

感谢你对 Image MultiModel 的关注！这是一个基于 ComfyUI 工作流引擎的多模型 AI 图像生成平台。

## 快速开始

1. Fork 本仓库并克隆：

```bash
git clone https://github.com/ReSerendipity/Image_MultiModel.git
cd Image_MultiModel
```

2. 安装依赖（系统 Python 3.10+，推荐 3.12）：

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
pip install -r requirements-lock.txt --require-hashes  # 可复现安装（可选）
```

3. 配置 `config.yaml`（ComfyUI 地址 / 模型路径 / 端口）后启动：

```bash
start.bat   # 或 python bin/clean_launch.py
```

## 开发规范

- **测试先行**：新增功能必须配套 pytest 测试，覆盖率目标 ≥75%
- **代码风格**：ruff check bin tests（配置文件见 pyproject.toml）
- **类型标注**：核心模块保持完整类型标注（mypy 检查）
- **提交信息**：使用 Conventional Commits 风格（feat / fix / docs / chore / test...）

## 常用命令

```bash
python -m pytest -q                          # 全量测试
python -m pytest tests/ -k smoke             # 冒烟测试
python -m ruff check bin tests               # 代码检查
python scripts/verify_watermark.py <img>     # 验证输出图像水印
```

## 分支与 PR

- 主分支 `main`，功能开发请新建分支
- PR 需通过 CI（lint + 测试 + SAST）后方可合并
- 提交前请运行 `python -m pytest -q` 确保本地全绿

## 问题反馈

- Bug / 功能建议：提交 [Issue](https://github.com/ReSerendipity/Image_MultiModel/issues)
- 安全问题：请通过 SECURITY.md 中的方式私下报告，勿公开披露

感谢你的贡献！
