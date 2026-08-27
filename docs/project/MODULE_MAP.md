“本文由 2026-08-27 家族治理 E3 从 AGENTS.md §3 移出，内容逐字保留”

# 模块边界（完整目录树）


```
Image_MultiModel/
├── app/
│   ├── integrated_app/          ← 主应用包（FastAPI + 业务 + 引擎适配）
│   │   ├── __init__.py          ← __version__ = "x.x.x"（版本号同步点 1/3）
│   │   ├── app_server.py        ← create_app() + lifespan（加载引擎 / 初始化 DB / SSE broker）
│   │   ├── clean_launch.py      ← 推荐入口（环境检测 + 配置加载 + 数据目录创建 + 健康检查）
│   │   ├── config.py            ← YAML 配置加载（原子写入 + 宽松/严格双接口）
│   │   ├── config_models.py     ← Pydantic AppConfig 模型（对应 config.yaml 全量字段）
│   │   ├── engine_interface.py  ← ImageEngine Protocol（load/unload/infer/cancel，所有引擎必须实现）
│   │   ├── exceptions.py        ← 全局异常类（统一继承 IntegratedAppError）
│   │   ├── gpu_utils.py         ← VRAM 估算 / NVIDIA-SMI 解析 / 精度推荐（FP8/FP16）
│   │   ├── history_db.py        ← SQLite（WAL + FTS5）历史记录 CRUD + 搜索 + ZIP 导出
│   │   ├── i18n.py              ← 后端错误文案国际化（5 语言 JSON，三层 fallback）
│   │   ├── model_manager.py     ← 引擎生命周期管理（加载/卸载/切换/状态监控）
│   │   ├── model_registry.py    ← 引擎注册表（根据 config.yaml 动态实例化）
│   │   ├── sse.py               ← SSE 事件 Broker（任务进度 / 系统状态实时推送）
│   │   ├── task_queue.py        ← 异步单 Worker 串行任务队列（批量 / 取消 / 断点恢复 checkpoint）
│   │   ├── watermark.py         ← DCT 频域数字水印嵌入 / 提取 / 验证（product_id + task_id + timestamp）
│   │   ├── native/              ← 原生进程内引擎（唯一引擎，backend: native，🚫 复用 comfy 源码需先 ensure_loaded）
│   │   │   ├── source.py        ← 把 comfy_kernel + aki-v3 自定义节点注入 sys.path（幂等）
│   │   │   ├── executor.py      ← 复用 comfy.sd / comfy.samplers 推理（加载→编码→采样→解码）
│   │   │   ├── engine.py        ← NativeEngine（ImageEngine 实现，输出落盘过 PathGuard）
│   │   │   ├── lora.py / seedvr.py / compares.py / vram.py / preview.py ← Phase 3 能力
│   │   ├── routes/              ← API 路由层（🚫 禁止写推理逻辑 / 业务逻辑）
│   │   │   ├── __init__.py      ← 手动 include_router 注册（⚠️ 新路由必须在这里加一行）
│   │   │   ├── config_routes.py ← /api/config/*（引擎列表 / 模型扫描 / 预设 CRUD）
│   │   │   ├── engine_routes.py ← /api/engine/*（加载/卸载/切换引擎）
│   │   │   ├── generate_routes.py ← /api/generate/*（文生图 / 批量 / SSE 进度）
│   │   │   ├── output_routes.py ← /api/output/*（生成结果图片 / ZIP 下载）
│   │   │   ├── preset_routes.py ← /api/preset/*（预设 CRUD / 导入导出）
│   │   │   ├── system_routes.py ← /api/system/*（健康检查 / 状态 / 版本）
│   │   │   └── task_routes.py   ← /api/task/*（任务列表 / 取消 / 断点恢复）
│   │   ├── middleware/          ← 中间件层（不包含业务逻辑）
│   │   │   ├── csrf.py          ← CSRF Token 头注入 + 校验
│   │   │   ├── error_handler.py ← 全局异常捕获 → 统一 JSON 错误响应（i18n 翻译）
│   │   │   ├── rate_limit.py    ← 三维度限流（推理 / 上传 / 全局）
│   │   │   └── request_id.py    ← 每个请求注入 X-Request-ID，日志全链路追踪
│   │   ├── security/            ← 安全模块（被路由层引用，自身不引用路由层）
│   │   │   ├── path_guard.py    ← PathGuard.resolve() 规范化校验（防 ../ 路径穿越）
│   │   │   ├── integrity_selfcheck.py ← 启动时完整性校验（SHA-256 vs integrity_manifest.json）
│   │   │   └── integrity_manifest.json ← 核心文件 SHA-256 清单
│   │   ├── locales/             ← 5 种语言翻译 JSON（zh / zh-tw / en / ja / ko）
│   │   └── static/              ← 前端单页应用（纯静态 index.html，无 Python 代码）
│   ├── install.bat / start.bat  ← Windows 一键（自动检测 WinPython / 系统 Python）
│   └── clean_launch.py          ← 被 start.bat 调用的入口（不要直接从根目录调这个）
├── workflows/                   ← ComfyUI 工作流 JSON（每引擎一份，可导入导出）
│   └── Z_image_turbo.json
├── model/           ← portable 模式唯一模型目录（独立运行时模型放这里；shared 模式直接走 shared.comfy_models_dir，不再用根目录链接）
├── tests/                       ← 测试体系（详见第 4 节）
│   ├── e2e/                     ← Playwright E2E 测试
│   └── *.py                     ← 单元 / 集成 / 安全测试
├── scripts/                     ← 辅助脚本
│   ├── benchmark.py             ← 性能基准（推理速度 / VRAM / batch 吞吐量）
│   ├── check_wcag.py            ← 前端 WCAG 2.1 AA 无障碍检查
│   ├── generate_integrity_manifest.py ← 重新生成 security/integrity_manifest.json
│   ├── migrate_outputs.py       ← 旧版本 outputs/ 目录迁移工具
│   ├── pack_portable.ps1        ← 打包便携版（含 WinPython + 模型；STEP 3 直接读 shared.comfy_models_dir 拷贝）
│   ├── setup_symlinks.ps1       ← 【已退役】不再创建根目录 Junction（shared 直接走 comfy_models_dir）
│   ├── test_portable_mode.py    ← 便携模式自检脚本
│   └── verify_watermark.py      ← DCT 水印 CLI 验证工具
├── docs/                        ← 文档（API / ARCHITECTURE / DEPLOYMENT / 健康度评估报告 / 截图）
├── examples/                    ← API 使用示例（Python 脚本 + prompts.txt）
├── prototypes/                  ← UI/UX 原型（Figma 对比 / 风格探索 / 多布局方案）
├── .github/                     ← CI/CD（详见第 9 节）
│   ├── workflows/               ← ci.yml / release.yml / security.yml
│   ├── ISSUE_TEMPLATE/          ← Bug / Feature Request 模板
│   └── PULL_REQUEST_TEMPLATE.md ← PR 模板
├── config.yaml                  ← 主配置文件（版本号同步点 2/3，禁止通过 API 修改 server.host）
├── CHANGELOG.md                 ← 变更日志（版本号同步点 3/3）
├── install.bat / install.sh     ← 跨平台依赖安装
├── start.bat / start.sh         ← 跨平台启动脚本
├── requirements.txt             ← 生产依赖
├── requirements-lock.txt        ← 锁定版本
├── pyproject.toml               ← 工具配置（Ruff / Mypy / Pytest / Coverage）
├── .pre-commit-config.yaml      ← Pre-commit 钩子
├── Dockerfile + docker-compose.yml ← 容器化部署
└── README.md / LICENSE / CONTRIBUTING.md / SECURITY.md / CODE_OF_CONDUCT.md ← 开源社区文件
```
