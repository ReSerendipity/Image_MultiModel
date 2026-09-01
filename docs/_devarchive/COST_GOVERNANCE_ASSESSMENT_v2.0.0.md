# Image_MultiModel v2.0.0 成本资源治理体系 · 深度完整性评估报告

> 评估类型：成本资源治理（FinOps / 资源利用 / 存储 / 网络）完整性评估
> 评估方法：基于源码与配置的证据驱动（evidence-based），逐条标注文件:行号
> 评估日期：2026-08-31
> 评估范围：`app/integrated_app/`、`config.yaml`、`scripts/`

---

## 0. 执行摘要（Executive Summary）

**总体结论：成本治理体系「局部成熟、整体缺位」。**

Image_MultiModel 当前架构是**本地优先（local-first）的单节点桌面工具**（监听 `127.0.0.1:8288`、portable 离线模式、`workers: 1`）。在这种形态下，许多云原生 FinOps 议题（24/7 常驻 GPU、Spot 实例、CDN、多实例模型去重）**当前并不触发成本**；但若将其作为**服务化部署**（多人共享、常驻、容器化），下列缺口将直接转化为真金白银的浪费。

| 子体系 | 成熟度 | 评级 | 一句话判断 |
|--------|:---:|:---:|------|
| ① GPU 资源利用率 | 中 | 🟡 B- | VRAM 预检与 FP8 回退扎实，但动态调度默认关闭、空闲不卸载、无自动伸缩 |
| ② 存储成本控制 | 低 | 🔴 C | 留存清理默认是**空操作**（no-op），PNG 无损无压缩，多引擎权重无版本去重 |
| ③ 网络传输优化 | 不适用/低 | ⚪ N/A→C | 纯离线 portable，无 CDN/带宽治理；多实例部署时存在「各自下载」风险 |
| ④ FinOps 实践 | 缺失 | 🔴 D | **零**成本核算、零预算告警、零 ROI、零成本看板 |

**最关键的三条反模式已在代码中实证成立：**
1. 「无存储清理自动化 → 磁盘写满」——`keep_days: 0` 导致 `history_cleanup_cron` 直接 `return`，清理任务形同虚设。
2. 「同一模型被多进程重复下载」——portable 模式每个实例各自维护 `model/`，无跨实例共享缓存（仅单实例内靠目录布局共享 VAE）。
3. 「成本可见性缺失」——GPU 监控仅以 SSE 推流，无任何持久化指标/成本看板（反模式 #5 成立）。

---

## 1. 评估前置条件与架构现实校验

在评估 GPU / 存储 / 网络成本之前，必须确认**成本实际发生的边界**。源码实证：

- **部署形态为单节点本地服务**：`config.yaml:3 server.host: 127.0.0.1`，`config.yaml:7 workers: 1`。
- **模型来源为便携离线**（`config.yaml:13 model_source_mode: portable`；`config.yaml:335-338` 强制 `HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE/MODELSCOPE_OFFLINE=1`）。即运行时**不发生任何模型下载流量**，也**不连外部 CDN**。
- **引擎唯一且进程内**：`config.yaml:34-162` 定义 3 个 `backend: native` 引擎（z_image_turbo_native / flux1_dev_fp8 / flux2_klein_9b），推理走 `NativeEngine`（`app/integrated_app/native/engine.py`），无外部 ComfyUI 进程。

> ⚠️ **治理前提提示**：本报告的「成本」在本地形态下主要表现为**电费 + 本地磁盘**；一旦服务化，将扩展为**GPU 实例时租 + 块存储 + 出口带宽 + 模型分发**。所有建议均按「当前本地 / 未来服务化」双视角给出。

---

## 2. 子体系一：GPU 资源利用率

### 2.1 VRAM 利用率（平均 vs 峰值）

**正向证据（成熟点）：**

- **显存预检体系完整且保守**：`gpu_utils.preflight_vram()`（`app/integrated_app/gpu_utils.py:148-249`）在每次推理前估算需求，公式含 `multisample_rule ×1.5` 安全系数（`gpu_utils.py:131`）、分辨率平方根缩放、batch 增量因子、SeedVR2 超分开销、LoRA 满精度增量（不随 fp8 缩放，防低估 OOM）。
- **FP8 自动回退**：显存不足时回退 fp8（约减半），`gpu_utils.py:201-203`；引擎默认精度即 `fp8`（`config.yaml:58/104/145`），基准显存预算仅 10–12 GB（`config.yaml:56/102/143`），天然偏向低成本。
- **显存泄漏监控器已就绪**：`VRAMLeakMonitor`（`gpu_utils.py:350-422`）可检测单调增长型泄漏（阈值 2 GB），并配有单测 `tests/test_vram_leak_monitor.py`。

**缺口（成本隐患）：**

- **动态 VRAM 调度默认关闭**：`config.yaml:228 vram_scheduler.enabled: false`。该调度器本应基于 `vram_high/low_watermark_pct` 在 `min_batch_size:1`~`max_batch_size:4` 间动态调节吞吐（`config.yaml:227-233`），关闭后**峰值/均值利用率无法自适应收敛到高位**，低显存机器易频繁触发保守的 chunk 拆分，吞吐偏低 = 单位图像 GPU 成本偏高。
- **泄漏监控未接入生产**：`VRAMLeakMonitor` 仅在 `scripts/perf_monitor.py` 与单测中被调用，**`app_server.py` 生命周期未实例化它**。即生产中无自动泄漏告警 → 长时间运行后显存碎片/泄漏会静默拉低有效利用率（对应其注释中的「反模式 #5」）。
- **峰值利用率不可观测为时间序列**：GPU 监控 `gpu_monitor_loop`（`app_server.py:238-253`）每 2s 向 SSE 推送 `gpu_status`，但**仅实时流、不入库存、不聚合**，无法事后分析「均值/峰值」比值，也无法评估空闲浪费。

### 2.2 空闲实例成本浪费（Idle waste）

- **模型常驻、空闲不卸载**：`NativeEngine.load()` 将权重注入显存（`native/engine.py:78-145`），`unload()` 仅 `soft_empty_cache`（`engine.py:147-157`）。队列空闲期（`task_queue.py` 单 Worker 轮询 `asyncio.sleep(0.2)`，`task_queue.py:173-178`）**无空闲检测、无自动卸载、无自动休眠**。在本形态下只是待机电费；服务化后即为「24/7 常驻 GPU 空载计费」（反模式 #1 的直接种子）。
- **无自动伸缩 / 无 Spot 感知**：`config.yaml:283-291 gpu` 仅有 `device_ids` 与 `low_vram_mode: auto`，无实例启停、无竞价/专用切换开关。

### 2.3 批处理（Batch）优化有效性

- **串行 Worker 防 OOM 是正确约束**：`runtime.task_queue.worker_mode: single_serial`（`config.yaml:210`），信号量=1，符合 AGENTS.md 硬约束 #4。**代价**是 GPU 无法靠并发摊薄固定开销，单图成本较高 → 更依赖 batch 摊薄。
- **batch 摊薄机制存在但偏弱**：`default_batch_size: 1`（`config.yaml:169`）；`preflight_vram` 在显存不足时推荐 chunk 拆分（`gpu_utils.py:219-225`，无超分时上限 16），`recommend_chunk_size` 同样上限 16（`gpu_utils.py:299-312`）。但调度器关闭后，batch 完全由用户手设，**无自动化把 batch 顶到显存允许上限**——意味着大量「本可 4 张一批」的请求被以「1 张一批」执行，单位图像成本约高 2–4 倍。
- **断点续跑避免重复计费**：`checkpoint.py` 在 `batch>500` 每 100 张落盘（`config.yaml:215 checkpoint_every: 100`），崩溃重启可恢复（`app_server.py:291-299` 扫描待恢复 checkpoint）。这是**减少算力浪费的有效设计**，值得肯定。

**GPU 子体系小结**：预检与回退是亮点，但「动态调度关闭 + 空闲不卸载 + 泄漏监控未上线 + 无利用率时序」使 GPU 利用率治理停留在「防崩」而非「降本」。

---

## 3. 子体系二：存储成本控制

### 3.1 模型去重（Model Deduplication）

- **单实例内存在路径级共享**：3 个引擎的 VAE 指向同一文件 `FLUX.1-dev(Z-image(turbo))/ae.safetensors`（`config.yaml:53/99/140`），`unet/text_encoder` 各自独立。**但** `weight_version: ''` 全空（`config.yaml:78/120/161`），`weight_sha256: ''` 全空 → **无版本钉死、无多版本共存治理**。若用户先后放入 `zimageTurboNSFWFP8` 与旧版权重，旧文件不会被识别/回收 = 静默重复占用。
- **跨实例去重机制已退役**：`scripts/setup_symlinks.ps1` 明确标注「**已退役（2026-08-13）**」，Junction 符号链接方案停用（`setup_symlinks.ps1:1-18`）。当前 portable 模式每个部署目录独立 `model/`，**云上多副本部署时，N 个实例 = N 份完整权重下载与存储**（反模式 #3）。
- **权重完整性校验 ≠ 去重**：`security/weight_integrity` 仅做 SHA/格式校验（`engine.py:97-128`），不比较/合并相同内容。

### 3.2 生成图像留存策略（Retention）—— 重大缺口

**实证反模式 #2（无清理自动化 → 磁盘写满）：**

- `config.yaml:191 output.history.keep_days: 0` 且 `config.yaml:192 cleanup_cron: "0 3 * * *"`。
- `app_server.py:256-263 history_cleanup_cron()` 开头即 `if not cron_expr or keep_days <= 0: return`（**直接返回，清理永不执行**）。
- 即便手动调用，`HistoryDB.cleanup_old_tasks(keep_days=0, max_gb=0)` 中 `keep_days>0` 与 `max_gb>0` 双条件都不满足 → 时间维度与**大小维度清理全部跳过**（`history_db.py:499-542`，默认 `keep_days=30` 但生产以 config 的 `0` 覆盖）。
- 唯一的「手动触发」端点 `POST /api/tasks/cleanup`（`routes/task_routes.py:179-182`）依赖运维主动调用，**无默认自动护栏**。

> 后果：默认配置下，生成图与历史记录**只增不减**（仅 `max_records: 50000` 上限，`config.yaml:190`，但 5 万条记录 + 对应 PNG 仍可能撑爆磁盘）。这是最确定的存储成本失控点。

### 3.3 压缩策略（Compression）

- **输出为无损 PNG，无有损/现代格式选项**：`output_pipeline.finalize_output` → `save_png(format="PNG")`（`native/output_pipeline.py:23-30, 81`）；`config.yaml:70-72 image_formats: [png]`、`default_format: png`（`config.yaml:170`）、`default_quality: 95`（`config.yaml:171`，但 PNG 忽略 quality，仅对 JPEG 生效 → 该配置实际无效）。
- **缩略图为 PNG**：`make_thumbnail(..., format="PNG")`，`thumbnail_max_side: 512`（`output_pipeline.py:50-64`，`config.yaml:187`）。512px PNG 缩略图相比 WebP 大 3–8 倍。
- **DCT 水印带来固定计算/存储开销**：每张图都做 `embed_provenance`（`output_pipeline.py:33-47`），属溯源合规必需，但增加 I/O 与轻微算力成本（可接受，建议在报告中标注为「合规成本」而非浪费）。
- **无按需转码/归档冷层**：生成图按 `engine/date` 平铺（`engine.py:216`，`config.yaml:185 organize_by: engine_date`），无生命周期分层（热/温/冷），无定期转 WebP 的后台任务。

**存储子体系小结**：留存清理是**默认关闭的空操作** + 全链路 PNG 无损 + 多版本权重无回收 + 跨实例去重已退役 = 存储治理成熟度最低，是四子体系中风险最高者。

---

## 4. 子体系三：网络传输优化

### 4.1 现状：纯离线，网络成本几乎为零

- `HF_HUB_OFFLINE=1 / TRANSFORMERS_OFFLINE=1 / MODELSCOPE_OFFLINE=1 / COMFYUI_DISABLE_UPDATE_CHECK=1`（`config.yaml:335-338`）→ 运行时**零模型下载、零检查更新流量**。
- 模型须在部署前就位（`engine.py:117-119` 对 `file_not_found` 仅跳过校验、不下载），即「懒加载」在此意为**首次推理时本地加载**，而非网络拉取。

### 4.2 服务化后的风险（当前 N/A，部署即触发）

- **CDN 缓存**：当前无静态资源 CDN（`app_server.py` 同源托管 `static/`/`templates/`）。高频访问的生成图走 `/api/outputs/<rel>` 直读本地盘，无边缘缓存。若对外服务，大图回源带宽将随并发线性增长。
- **大文件懒加载**：权重懒加载仅限**单实例首次推理**，无跨节点预取/分片。多实例同时冷启动会并发打满内网/对象存储带宽（反模式 #3 的网络侧表现）。
- **下载带宽限流**：全局**无任何 throttling 配置**（`config.yaml` 无 bandwidth/rate 项；`security.rate_limit` 仅限 API 请求数 `infer_per_minute: 30`，`config.yaml:244-247`，不限字节数）。服务化时模型分发可能挤占推理带宽。

**网络子体系小结**：本地形态下成本可忽略（优势）；但缺乏「模型分发/缓存/限流」任何抽象，意味着**从桌面到服务的迁移成本被低估**，网络治理能力实质缺失。

---

## 5. 子体系四：FinOps 实践

### 5.1 成本分摊（Cost Allocation by feature/user）

- **无任何按功能/用户计费维度**。历史库 `history_db.py` 记录 `engine / mode / prompt / processing_time_s / output_count`（`history_db.py:33-65`），`processing_time_s` 是**唯一可映射算力的字段**，但：
  - 无用户/租户字段（本地单用户，服务化后需补 `user_id/tenant_id`）；
  - 无显存/能耗计量；
  - 无将 `processing_time_s` 折算为 GPU·小时的报表或接口。
- 即：**具备原始数据，缺乏归集与分摊**。

### 5.2 预算告警（Budget Alerts）

- **全局零预算/阈值/告警**。搜索 `cost|billing|budget|finops` 在后端代码中**无命中**（仅前端文案提及，非 FinOps 设施）。GPU 监控有阈值 `vram_high_watermark_pct: 90`（`config.yaml:229`）但是**显存水位**而非**金额预算**，且无超阈通知通道（仅 SSE 流）。

### 5.3 ROI 分析

- **无基础设施投资回报评估**。存在 `scripts/benchmark.py`（P95/P99 延迟、TTFP 等，`benchmark.py:1-12`）与 `scripts/perf_monitor.py`（泄漏监控），属**性能基准**而非**成本 ROI**。无法回答「上更大 GPU 是否划算」「FP8 vs bf16 的单位图像成本差」等 ROI 问题。

### 5.4 成本可见性（Dashboards）—— 反模式 #5 实证

- GPU 状态每 2s SSE 推送但**不入库存、无看板**（`app_server.py:238-253`）；
- 无 `/metrics`、无 Prometheus 暴露、无 Grafana 类面板；
- `VRAMLeakMonitor` 未接入生产（见 2.1）。
- 即运维**看不到** GPU 利用率曲线、存储增长曲线、单位请求成本 —— 成本黑盒。

**FinOps 子体系小结**：四个支柱（分摊/告警/ROI/可见性）**全部缺失**。现有 `processing_time_s` 是唯一可复用数据源，是搭建 FinOps 的最小可行起点。

---

## 6. 反模式识别对照表（与用户清单逐条映射）

| # | 反模式 | 是否在代码中实证 | 证据 | 严重度 |
|---|--------|:---:|------|:---:|
| 1 | 低峰期 24/7 常驻 GPU | ⚠️ 种子已埋（本地形态暂未计费） | 无空闲卸载/自动休眠（`task_queue.py:173-178`、`engine.py:147-157`）；`auto_load_default_engine: false` 仅省冷启动内存，不省空载 | 🟡 中（服务化后高） |
| 2 | 无存储清理 → 磁盘写满 | ✅ **实锤** | `keep_days: 0` → `history_cleanup_cron` 直接 return（`app_server.py:261`）；`max_gb: 0` 双维度跳过（`history_db.py:513-537`） | 🔴 高 |
| 3 | 同模型被多进程重复下载 | ✅ 单实例内已共享 VAE；⚠️ 跨实例无共享 | 去重脚本退役（`setup_symlinks.ps1:1-18`）；portable 每实例独立 `model/`（`config.yaml:13/26`） | 🔴 高（服务化） |
| 4 | 过度配置（GPU 过大） | ⚠️ 部分缓解 | 默认 fp8 + 10–12GB 预算（`config.yaml:56-143`），`low_vram_mode: auto`；但无自动选型/伸缩，仍可能配大卡闲置 | 🟡 中 |
| 5 | 成本可见性缺失（无看板） | ✅ **实锤** | GPU 仅 SSE 流不持久化（`app_server.py:238-253`）；无 metrics/看板；`VRAMLeakMonitor` 未上线 | 🔴 高 |

---

## 7. 特别警示：AI 推理成本权衡矩阵

| 权衡维度 | 当前项目立场 | 成本影响 | 治理建议 |
|----------|------------|---------|---------|
| **质量 vs 成本**（低分辨率更便宜但 UX 差） | 默认 `1024×1024`（`config.yaml:66-67`），`default_steps: 10`（`config.yaml:164`，Turbo 低步数本就省成本） | 低步数+fp8 已是对成本友好的默认；但**无按成本档位（如 512 草图 / 1024 成品）的计费区分** | 引入「质量档位→预估成本」映射，前端展示单价 |
| **预加载模型**（省冷启动但费内存） | `auto_load_default_engine: false`（`config.yaml:6`）→ **懒加载**，省常驻内存但首请求慢 | 本地形态降本（不占空载显存）；服务化常驻场景应改为按需预热 | 加 `preload_on_startup` 按部署形态切换 |
| **Spot vs 专用**（省钱 vs 可靠） | 无相关抽象 | 当前无关；服务化时若用 Spot，需配合 checkpoint 续跑（`checkpoint.py` 已具备）避免中断浪费 | Spot + 断点续跑 = 天然适配，建议服务化时优先启用 |

> 结论：项目在「质量/成本」与「预加载」上已有合理默认（低步数、fp8、懒加载），但**全部是隐式默认值，无显式成本标签**，用户无法做知情权衡。

---

## 8. 治理完整性附加发现（跨子体系）

- **版本号三处不一致（治理流程缺口）**：`config.yaml:1 version: 1.4.0`，但提问基于 `v2.0.0`、且 `AGENTS.md` 顶部声明 `v2.0.0`、自进化修订表却止于 v1.4。违反 AGENTS.md §9.2「三处同步」铁律与自检 #7。**成本治理依赖的「版本→配置契约」不可信**，建议先修复再发版。
- **GPU 监控历史窗口过小**：`gpu.monitor.history_points: 60`（`config.yaml:291`，即 2min×60=2min 滚动），无法做日/周级利用率趋势，直接限制成本分析深度。
- **断点续跑是亮点**：`checkpoint_every: 100`、`batch>500`（`checkpoint.py`、`config.yaml:215`）避免崩溃重算，是少数直接「省算力」的设计，建议保留并在服务化时强化。

---

## 9. 优先级整改路线图（Recommendations）

> 标注 [本地] 当前形态即应做；[服务化] 仅部署为服务时需做。

| 优先级 | 整改项 | 对应反模式 | 落地建议 | 预期收益 |
|:---:|------|:---:|------|------|
| P0 | **开启留存清理护栏** | #2 | `keep_days` 设为 30（或 `max_gb` 设上限如 50），或至少让 `history_cleanup_cron` 在 `keep_days<=0` 时退化为按 `max_gb` 清理 | 杜绝磁盘写满导致服务中断 |
| P0 | **输出格式可选 WebP/有损** | 存储 | `image_formats` 增加 webp，`default_quality` 对 webp 生效；缩略图改 webp | 存储下降 60–90% |
| P1 | **上线 VRAM 利用率持久化 + 看板** | #5 | 将 `gpu_monitor_loop` 写入时序库/暴露 `/metrics`；接入 `VRAMLeakMonitor` | 成本可见性从 0→1 |
| P1 | **多版本权重回收** | #3(单实例) | `weight_version/sha256` 落地，启动扫描 `model/` 孤儿权重并告警/清理 | 回收数 GB~数十 GB |
| P1 | **启用 vram_scheduler** | GPU 利用率 | `vram_scheduler.enabled: true`，让 batch 自动顶到显存上限 | 单位图像 GPU 成本降 2–4× |
| P2 | **空闲自动卸载/休眠** | #1 | 队列空闲 N 分钟触发 `unload()` + 可选停实例 | 服务化空载计费归零 |
| P2 | **FinOps 最小闭环** | #5/分摊 | 用现有 `processing_time_s` + `engine` 推出「GPU·小时/引擎」报表接口 | 成本分摊可起步 |
| P2 | **跨实例模型共享缓存** | #3 | 对象存储/共享卷挂载 `model/`，替代退役的 Junction | 多副本部署权重存储/下载 ×N→1 |
| P3 | **预算告警 + ROI 看板** | 全部 | 金额预算阈值 + 通知；FP8 vs bf16 单位成本对比 | 闭环 FinOps |
| P3 | **修复版本号三处同步** | 治理 | `config.yaml`/`__init__.py`/`CHANGELOG.md` 对齐到 2.0.0 | 恢复配置契约可信度 |

---

## 10. 成本量化粗估（供优先级排序参考，非精确账单）

假设服务化在一张 ~24GB 消费级/数据中心 GPU 上：

- **GPU 时租**：若常驻 24/7 不卸载（反模式 #1 种子)= 全额时租；开启空闲卸载后可削减低峰 ~40–60% 计费。
- **存储**：默认 PNG 1024² 单图约 1–3 MB；5 万条上限 + 缩略图，轻松达 **数十~数百 GB**；改 WebP 后降至 **数 GB 级**。留存 `keep_days:0` 不设防时，按日产出千图计，数月即触顶本地盘。
- **模型**：3 引擎完整权重（unet bf16/fp8 + 文本编码器 4–8B fp8 + VAE）合计约 **30–60 GB**；跨实例去重缺失时 N 副本线性放大。
- **算力摊薄**：batch 从 1 提到调度器上限 4（启用 `vram_scheduler`），理论上单位图像推理耗时降约 40–60%，即单位成本同步下降。

> 注：以上为基于配置与常见权重大小的**量级估算**，精确值需在目标硬件上以 `scripts/benchmark.py` + 新增成本埋点实测。

---

## 11. 结语

Image_MultiModel v2.0.0 在**防止 GPU OOM（预检/FP8/串行）**与**防止算力浪费（断点续跑）**上设计成熟，体现了工程克制；但**成本治理作为一个独立体系几乎不存在**——留存清理默认空转、全链路 PNG 无损、显存监控不入库存、FinOps 四支柱全缺、跨实例去重已退役。

对于**当前本地形态**：最紧急的是 P0（开启留存护栏 + 输出压缩），否则磁盘必然写满。
对于**未来服务化形态**：P1–P3 的「利用率持久化 + 动态调度 + 空闲卸载 + FinOps 闭环 + 模型共享缓存」是避免成本失控的必需项。

**治理成熟度综合评分：GPU 防崩 B- / 存储 C / 网络 N/A→C / FinOps D；整体处于「有健壮性、无经济性」阶段。**
