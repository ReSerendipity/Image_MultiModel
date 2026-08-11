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


---

## 提交前必做（本地门禁）

> 目标：让每一次提交都能顺利通过 CI，而不是反复修。

### 安装 git hooks（一次即可）

``powershell
powershell -ExecutionPolicy Bypass -File scripts/install-hooks.ps1
``

之后每次 git push 前自动跑**快检**（ruff / 格式 / compileall 语法 / UTF-8 编码扫描），不过会阻止推送。也可手动：

``bash
python scripts/check_local.py          # 快检（秒级）
python scripts/check_local.py --full   # 快检 + 全量 pytest
``

> CI 是唯一权威门禁。git push --no-verify 可绕过（不推荐）。

### 编码卫生（防乱码）

- 所有源码/文本文件必须为 UTF-8 无 BOM（.gitattributes 已统一 LF 行尾）
- 禁止用第三方编码转换工具批量改写源文件后直接提交（曾导致中文乱码 SyntaxError）
- 本地检查会自动扫描全部被跟踪文本文件的 UTF-8 合法性

### 新增依赖

- 运行依赖 → equirements.txt；测试/开发依赖 → equirements-dev.txt（TTS 可并入 requirements 或建 dev 文件）
- 不要只 pip install 后就不管：CI 从干净环境只装 requirements，漏写必红
- 测试工具链尽量固定版本（防漂移）；TTS 的 playwright 已固定 1.62.0

### 覆盖率门槛

- 只在 CI 判定（跨平台数值有差异，本地不判）；CI 红在覆盖率时补测试而不是调门槛

### CI 红了先看什么

| 现象 | 常见根因 | 处理 |
|---|---------|------|
| cancelled | 连续 push 取消旧 run | **不是失败**，看最新 run |
| ruff/black 红 | 没跑本地门禁 | python scripts/check_local.py 修复后重推 |
| mypy 红 | 类型错误 | 本地 python -m mypy bin/integrated_app 先修 |
| pytest 红 | 测试失败/缺依赖 | 本地 --full 复现；缺依赖补 requirements |
| 覆盖率红 | 新代码没测 | 补测试 |
| SyntaxError/乱码 | 编码损坏 | 本地 UTF-8 扫描定位修复 |
| E2E 视觉回归红（TTS） | UI 改动未更新 baseline | 触发 Update Baselines 工作流（见下） |
| E2E 超时取消 | 测试量大/个别慢 | 日志定位慢测试；必要时提高 job 超时 |

### 视觉回归 baseline 更新（仅 TTS_MultiModel）

改了 UI/样式后视觉回归会红。在 GitHub Actions 页面手动触发 **Update Baselines** 工作流（CI/Linux 环境生成并自动提交）。**不要**在 Windows 本地生成 baseline 提交（渲染环境不同会反复红）。

### 提交节奏

- push 后等 CI 出结果再推下一个 commit（避免旧 run 被取消）
- 检查 CI 状态以最新 HEAD 的 run 为准
