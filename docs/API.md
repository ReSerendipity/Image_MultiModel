# API 文档 (API Reference)

Image MultiModel 提供 REST API 和 SSE 事件流，支持程序化调用。

> **在线文档**：启动服务器后访问 `http://127.0.0.1:8288/docs`（FastAPI Swagger UI）
>
> **示例代码**：参见 [examples/](../examples/) 目录

---

## 目录

- [系统](#系统)
- [生成](#生成)
- [任务](#任务)
- [引擎](#引擎)
- [配置](#配置)
- [预设](#预设)
- [输出](#输出)
- [SSE 事件流](#sse-事件流)

---

## 系统

### GET /api/health

健康检查 — 返回后端、引擎、GPU、磁盘状态摘要。

**请求**：无参数

**响应**：
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": 1723286400.0,
  "server": {
    "host": "127.0.0.1",
    "port": 8288
  },
  "gpu": {
    "name": "NVIDIA RTX 5070 Ti",
    "backend": "cuda",
    "total_vram_gb": 12.0,
    "free_vram_gb": 8.5
  },
  "disk": {
    "total_gb": 500.0,
    "used_gb": 300.0,
    "free_gb": 200.0
  },
  "engines": [
    {
      "name": "z_image_turbo_native",
      "display_name": "Z-Image Turbo",
      "ready": false,
      "active": true
    }
  ],
  "queue": {}
}
```

**示例**：
```bash
curl http://127.0.0.1:8288/api/health
```

---

### GET /api/gpu

GPU 状态 — 返回当前 GPU 显存使用情况。

**响应**：
```json
{
  "name": "NVIDIA RTX 5070 Ti",
  "backend": "cuda",
  "total_vram_gb": 12.0,
  "used_vram_gb": 3.5,
  "free_vram_gb": 8.5
}
```

---

## 生成

### POST /api/generate

提交文生图任务。

**请求体**：
```json
{
  "positive_prompt": "a serene mountain landscape at golden hour",
  "negative_prompt": "blurry, low quality",
  "cfg": 1.0,
  "steps": 8,
  "width": 1024,
  "height": 1024,
  "seed": -1,
  "batch_size": 1,
  "lora_1_name": "",
  "lora_1_strength": 1.0,
  "lora_2_name": "",
  "lora_2_strength": 0.7,
  "lora_3_name": "",
  "lora_3_strength": 0.5,
  "lora_4_name": "",
  "lora_4_strength": 0.4,
  "lora_5_name": "",
  "lora_5_strength": 0.3,
  "lora_6_name": "",
  "lora_6_strength": 0.2,
  "seedvr2_enable": true,
  "seedvr2_resolution": 2048,
  "seedvr2_seed": -1,
  "seedvr2_color_correction": "lab",
  "eses_enable": true,
  "eses_compare_axis": "horizontal",
  "vram_enable": true,
  "vram_reserved_gb": 0.6,
  "vram_mode": "auto",
  "vram_seed": -1,
  "output_format": "png",
  "output_prefix": "",
  "engine_name": "z_image_turbo_native"
}
```

**参数说明**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `positive_prompt` | string | `""` | 正向 Prompt |
| `negative_prompt` | string | `""` | 负向 Prompt |
| `cfg` | float | `1.0` | CFG Scale（引导系数） |
| `steps` | int | `8` | 采样步数 |
| `width` | int | `1024` | 图片宽度 |
| `height` | int | `1024` | 图片高度 |
| `seed` | int | `-1` | 随机种子（-1 = 随机） |
| `batch_size` | int | `1` | 批量大小（1~9999） |
| `lora_1_name` ~ `lora_6_name` | string | `""` | LoRA 文件名（6层叠加） |
| `lora_1_strength` ~ `lora_6_strength` | float | 1.0~0.2 | LoRA 强度 |
| `seedvr2_enable` | bool | `true` | 是否启用 SeedVR2 超分 |
| `seedvr2_resolution` | int | `2048` | 超分目标分辨率 |
| `seedvr2_seed` | int | `-1` | 超分种子 |
| `seedvr2_color_correction` | string | `"lab"` | 色彩校正模式 |
| `eses_enable` | bool | `true` | 是否启用 Eses 对比 |
| `eses_compare_axis` | string | `"horizontal"` | 对比轴方向 |
| `vram_enable` | bool | `true` | 是否启用 VRAM 预留 |
| `vram_reserved_gb` | float | `0.6` | 预留显存（GB） |
| `vram_mode` | string | `"auto"` | VRAM 模式 |
| `vram_seed` | int | `-1` | VRAM 种子 |
| `output_format` | string | `"png"` | 输出格式 |
| `output_prefix` | string | `""` | 文件名前缀 |
| `engine_name` | string\|null | `null` | 引擎名称（null = 默认引擎） |

**响应**：
```json
{
  "task_id": "01J5A3B2C...",
  "status": "pending",
  "estimated_time_s": 5.0,
  "estimated_vram_gb": 11.0,
  "warning": null
}
```

**错误码**：
- `404` — 引擎不存在
- `400` — batch_size 超出范围 / 显存不足
- `503` — 任务队列已满

**示例**：
```bash
curl -X POST http://127.0.0.1:8288/api/generate \
  -H "Content-Type: application/json" \
  -d '{"positive_prompt":"a cat","engine_name":"z_image_turbo_native"}'
```

---

### POST /api/generate/batch

批量生成 — 支持 Prompt 列表 x Grid 参数网格笛卡尔积。

**请求体**：
```json
{
  "prompts": ["prompt A", "prompt B"],
  "prompt_file": null,
  "grid_dimensions": {
    "cfg": [1.0, 3.5],
    "steps": [4, 8]
  },
  "base_config": {
    "positive_prompt": "",
    "cfg": 1.0,
    "steps": 8,
    "width": 1024,
    "height": 1024,
    "seed": -1,
    "batch_size": 1,
    "engine_name": "z_image_turbo_native",
    "seedvr2_enable": false
  }
}
```

**响应**：
```json
{
  "batch_id": "01J5A3B2C...",
  "total_tasks": 8,
  "task_ids": ["01J5A...", "01J5A...", "..."]
}
```

**Grid 展开**：2 prompts x 2 cfg x 2 steps = 8 tasks

---

### GET /api/tasks/batch/{batch_id}

查询批量任务进度。

**路径参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `batch_id` | string | 批次 ID |

**响应**：
```json
{
  "batch_id": "01J5A3B2C...",
  "total": 8,
  "completed": 3,
  "failed": 0,
  "cancelled": 0,
  "processing": 1,
  "pending": 4,
  "progress_pct": 37
}
```

---

## 任务

### GET /api/tasks

历史记录列表 — 支持分页、搜索、筛选。

**查询参数**：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `status` | string | null | 按状态筛选（pending/processing/completed/failed/cancelled） |
| `engine` | string | null | 按引擎筛选 |
| `q` | string | null | 搜索关键词（Prompt 全文检索） |
| `favorite` | bool | null | 按收藏筛选 |
| `page` | int | 1 | 页码（从 1 开始） |
| `page_size` | int | 50 | 每页条数（1~200） |

**响应**：
```json
{
  "tasks": [
    {
      "task_id": "01J5A3B2C...",
      "engine": "z_image_turbo_native",
      "mode": "txt2img",
      "status": "completed",
      "prompt": "a cat",
      "thumbnail": "outputs/...",
      "output_count": 3,
      "processing_time_s": 12.5,
      "created_at": 1723286400
    }
  ],
  "total": 286,
  "page": 1,
  "page_size": 50,
  "total_pages": 6
}
```

---

### GET /api/tasks/{task_id}

任务详情 — 包含完整 generation_config（22项）和输出文件列表。

**响应**：
```json
{
  "task_id": "01J5A3B2C...",
  "engine": "z_image_turbo_native",
  "mode": "txt2img",
  "status": "completed",
  "prompt": "a cat",
  "negative_prompt": "blurry",
  "generation_config": {
    "cfg": 1.0,
    "steps": 8,
    "width": 1024,
    "height": 1024,
    "seed": 42,
    "batch_size": 1
  },
  "outputs": [
    {
      "path": "z_image_turbo_native/20260810/task_id_original.png",
      "output_type": "original",
      "format": "png",
      "file_size": 4567890,
      "width": 1024,
      "height": 1024
    },
    {
      "path": "z_image_turbo_native/20260810/task_id_upscaled.png",
      "output_type": "upscaled"
    },
    {
      "path": "z_image_turbo_native/20260810/task_id_compare.png",
      "output_type": "compare"
    }
  ],
  "processing_time_s": 12.5,
  "created_at": 1723286400,
  "favorite": false,
  "tags": []
}
```

---

### POST /api/tasks/{task_id}/cancel

取消任务 — 调用 ComfyUI `/interrupt` + 队列清理。

**响应**：
```json
{
  "status": "cancelled",
  "task_id": "01J5A3B2C..."
}
```

---

### POST /api/tasks/{task_id}/redraw

使用相同参数重绘 — 从历史记录恢复参数并提交新任务。

**响应**：
```json
{
  "task_id": "01J5A3B2C_new...",
  "status": "pending",
  "source_task_id": "01J5A3B2C_original..."
}
```

---

### DELETE /api/tasks

批量删除任务。

**查询参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `task_ids` | list[string] | 要删除的任务 ID 列表 |

**响应**：
```json
{
  "deleted": 5
}
```

---

### GET /api/tasks/export

导出任务图片为 ZIP。

**查询参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `ids` | string | 逗号分隔的任务 ID |
| `type` | string\|null | 输出类型筛选（original/upscaled/compare） |

**响应**：`application/zip` 文件下载

---

### POST /api/tasks/tags

批量添加标签。

**查询参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `task_ids` | list[string] | 任务 ID 列表 |
| `tags` | list[string] | 标签列表 |

**响应**：
```json
{
  "tagged": 5
}
```

---

### POST /api/tasks/cleanup

清理超期任务。

**查询参数**：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `keep_days` | int | 30 | 保留天数 |
| `max_gb` | float | 0 | 最大存储 GB（0 = 不限） |

**响应**：
```json
{
  "deleted": 15,
  "keep_days": 30,
  "max_gb": 0
}
```

---

## 引擎

### GET /api/engine/engines

引擎列表 — 包含元数据和加载状态。

**响应**：
```json
{
  "engines": [
    {
      "name": "z_image_turbo_native",
      "display_name": "Z-Image Turbo",
      "display_name_en": "Z-Image Turbo",
      "ready": false,
      "state": "unloaded",
      "active": true,
      "vram_gb": 11.0,
      "ram_gb": 24.0,
      "default_precision": "fp8",
      "supported_features": ["txt2img", "lora_stack_6", "seedvr2_upscale_2x"],
      "tags": ["realistic", "high-quality", "distilled", "fast"]
    }
  ],
  "active_engine": "z_image_turbo_native",
  "count": 1
}
```

---

### POST /api/engine/load

加载引擎 — 触发模型加载流程，通过 SSE `model_status` 推送进度。

**请求体**：
```json
{
  "engine_name": "z_image_turbo_native"
}
```

**响应**：
```json
{
  "engine_name": "z_image_turbo_native",
  "status": "loaded",
  "message": "Engine 'Z-Image Turbo' loaded successfully"
}
```

---

### POST /api/engine/unload

卸载当前引擎 — 释放模型占用的显存。

**响应**：
```json
{
  "engine_name": "z_image_turbo_native",
  "status": "unloaded",
  "message": "Engine 'z_image_turbo_native' unloaded"
}
```

---

### POST /api/engine/free

释放 ComfyUI 显存 — 转发 ComfyUI `/free` 请求，清空未使用模型缓存。

**响应**：
```json
{
  "status": "ok",
  "message": "VRAM freed"
}
```

---

## 配置

### GET /api/config

读取配置 — 返回脱敏后的配置（不包含密码/Token 等敏感字段）。

**响应**：
```json
{
  "version": "1.0.0",
  "inference": {
    "default_steps": 10,
    "default_cfg": 1.0,
    "vram_headroom_gb": 2.0
  },
  "output": {
    "base_dir": "outputs",
    "history": {
      "db_path": "data/history.db",
      "keep_days": 0
    }
  },
  "ui": {
    "theme_default": "light",
    "accent_color": "#5e7d5a"
  },
  "i18n": {
    "default_locale": "zh",
    "available_locales": ["zh", "en", "ja", "ko", "zh-tw"]
  }
}
```

---

### PUT /api/config

更新配置 — 部分更新，写回 `config.yaml`。`host` 字段只读，不允许通过 API 修改。

**请求体**：
```json
{
  "inference": {
    "default_steps": 12
  },
  "ui": {
    "theme_default": "dark"
  }
}
```

**响应**：
```json
{
  "status": "ok",
  "message": "Config saved successfully"
}
```

---

### GET /api/config/loras

扫描 LoRA 目录 — 返回可用的 LoRA 文件列表（前端下拉用）。

**响应**：
```json
{
  "loras": [
    "style_name.safetensors",
    "character_name.safetensors"
  ],
  "count": 64,
  "mode": "shared"
}
```

---

## 预设

### GET /api/presets

列出预设。

**查询参数**：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `engine_name` | string | null | 按引擎筛选 |

**响应**：
```json
[
  {
    "id": 1,
    "engine_name": "z_image_turbo_native",
    "name": "人像摄影",
    "thumbnail": "",
    "config": {
      "cfg": 1.0,
      "steps": 10,
      "width": 1024,
      "height": 1024
    },
    "created_at": 1723286400
  }
]
```

---

### POST /api/presets

创建预设。

**请求体**：
```json
{
  "engine_name": "z_image_turbo_native",
  "name": "风景摄影",
  "config": {
    "cfg": 1.0,
    "steps": 8,
    "width": 1024,
    "height": 1024,
    "seedvr2_enable": true
  },
  "thumbnail": ""
}
```

**响应**：
```json
{
  "id": 2,
  "status": "created"
}
```

---

### GET /api/presets/{preset_id}

获取预设详情。

---

### PUT /api/presets/{preset_id}

更新预设。

**请求体**：
```json
{
  "name": "风景摄影 v2",
  "config": {
    "steps": 12
  }
}
```

---

### DELETE /api/presets/{preset_id}

删除预设。

---

### POST /api/presets/{preset_id}/apply

应用预设 — 返回参数供前端回填。

**响应**：
```json
{
  "status": "applied",
  "engine_name": "z_image_turbo_native",
  "config": {
    "cfg": 1.0,
    "steps": 10,
    "width": 1024,
    "height": 1024
  }
}
```

---

### POST /api/presets/import

批量导入预设。

**请求体**：
```json
[
  {
    "engine_name": "z_image_turbo_native",
    "name": "预设1",
    "config": {}
  },
  {
    "engine_name": "z_image_turbo_native",
    "name": "预设2",
    "config": {}
  }
]
```

**响应**：
```json
{
  "imported": 2,
  "errors": []
}
```

---

### GET /api/presets/export

导出所有预设（可按引擎筛选）。

---

## 输出

### GET /api/outputs

图库列表 — 返回真实文件列表（含宽高用于 masonry 布局）。

**查询参数**：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | string | null | 按输出类型筛选（original/upscaled/compare） |
| `fav` | bool | null | 按收藏筛选 |
| `page` | int | 1 | 页码 |
| `page_size` | int | 50 | 每页条数 |

**响应**：
```json
{
  "outputs": [
    {
      "path": "z_image_turbo_native/20260810/xxx_original.png",
      "output_type": "original",
      "format": "png",
      "file_size": 4567890,
      "width": 1024,
      "height": 1024,
      "favorite": false,
      "task_id": "01J5A3B2C..."
    }
  ],
  "total": 573,
  "page": 1,
  "page_size": 50
}
```

---

### GET /api/outputs/{file_path}

获取输出图片（返回图片文件）。

---

### POST /api/outputs/{file_path}/fav

收藏/取消收藏输出图片。

**响应**：
```json
{
  "status": "favorited",
  "path": "outputs/z_image_turbo_native/20260810/xxx_original.png"
}
```

---

### GET /api/outputs/{file_path}/download

下载输出图片（返回文件流，带 Content-Disposition: attachment）。

---

## SSE 事件流

### GET /api/events

SSE 单连接事件总线 — 前端建立一个 `EventSource` 连接，接收所有事件类型。

**事件类型**：

| 事件 | 说明 | 数据示例 |
|------|------|----------|
| `connected` | 连接建立 | `{"type":"connected","timestamp":1723286400}` |
| `heartbeat` | 心跳（30s） | `{"timestamp":1723286400}` |
| `task_status` | 任务状态变更 | `{"task_id":"...","progress":0.5,"status":"processing","phase":"sampling"}` |
| `comfy_preview` | 采样中预览图 | `{"task_id":"...","b64":"data:image/jpeg;base64,...","format":"jpg"}` |
| `gpu_status` | GPU 状态（2s） | `{"name":"RTX 5070 Ti","total_vram_gb":12,"used_vram_gb":3.5,"free_vram_gb":8.5}` |
| `model_status` | 引擎加载状态 | `{"engine":"z_image_turbo_native","state":"loading"}` |
| `queue_status` | 队列状态 | `{"pending":3,"processing":1,"completed":10}` |

**前端监听示例**：
```javascript
const evt = new EventSource('/api/events');

evt.addEventListener('task_status', (e) => {
  const data = JSON.parse(e.data);
  console.log(`Task ${data.task_id}: ${data.progress * 100}% - ${data.status}`);
});

evt.addEventListener('gpu_status', (e) => {
  const data = JSON.parse(e.data);
  console.log(`GPU: ${data.used_vram_gb}/${data.total_vram_gb} GB`);
});

evt.addEventListener('comfy_preview', (e) => {
  const data = JSON.parse(e.data);
  document.getElementById('preview').src = data.b64;
});
```

**cURL 监听示例**：
```bash
curl -N http://127.0.0.1:8288/api/events
```

**Nginx 代理注意**：SSE 是长连接，必须设置 `proxy_buffering off;`，否则事件会被缓冲不推送。详见 [部署指南](DEPLOYMENT.md#②-反向代理配置)。
