# Image_MultiModel — 文档与项目速览

> 图像生成 Web 应用（多引擎：原生 CUDA + diffusers）。FastAPI 后端 + 原生 JS 前端。
> 入口：`app/clean_launch.py` / `start.bat`（默认端口 **8288**）。
> 详细目录放置规则见 `AGENTS.md` 末尾「文件归档与放置规范」。

## 快速了解本项目
- **做什么**：文生图 / 图生图 / 批量生成 / 预设 / 历史记录，支持原生引擎切换。
- **技术栈**：Python · FastAPI · CUDA(torch cu132) · 原生 JS/CSS（SPA）。
- **如何启动**：`start.bat` 或 `python app/clean_launch.py`，浏览器打开 `http://127.0.0.1:8288`。

## 目录结构速览
| 目录 | 内容 |
|---|---|
| `app/integrated_app/` | **主程序源码**（routes/ native/ middleware/ security/ static/ templates/） |
| `tests/` | 后端 pytest + `tests/frontend`(Playwright smoke) |
| `docs/` | 项目文档（见下方 docs 索引） |
| `model/` | 模型权重（unet/ vae/ text_encoders/ loras） |
| `data/` | 运行时数据（cache/ checkpoints/ uploads/ history.db） |
| `workflows/` | Comfy 工作流 JSON |
| `examples/` | API 用法示例脚本 |
| `demo/` | HTML 演示页 |
| `scripts/` | 运维/工具脚本 |

> ⚠️ 注意：历史文档若写到 `bin/integrated_app/...`，那是改名前的旧路径；**真实代码在 `app/integrated_app/`**。

## docs/ 索引（本目录）
| 子目录/文件 | 存什么 |
|---|---|
| `project/` | 架构(ARCHITECTURE)、API、路径配置、PRD |
| `plans/` | 实施指南、重构/独立计划、部署、待办 |
| `reports/` | 健康度/功能状态、审计(AUDIT/LOGGING/TEST)、遗留任务 |
| `repo-analysis/` | 参考仓库学习报告（`{仓库}_技术学习报告.md`） |
| `_devarchive/` | 历史/一次性开发产物（归档区） |
| `screenshots/` | 界面截图 |
| `THIRD_PARTY_NOTICES` / `COMPLIANCE_CHECKLIST` | 合规声明（根目录） |

## 想找内容？
- 想改生成逻辑 → `app/integrated_app/native/`、`app/integrated_app/routes/generate_routes.py`
- 想改前端 → `app/integrated_app/static/index.html` + `static/js/app.js`
- 想改配置 → `config.yaml`（含模型来源/路径/引擎）
- 想加测试 → `tests/`
- 想了解功能范围 → `docs/reports/功能实现状态分析报告.md`