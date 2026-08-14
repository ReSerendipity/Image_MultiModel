# Fooocus 开源仓库技术分析报告

> 仓库地址：https://github.com/lllyasviel/Fooocus
> 分析日期：2026-08-13
> 报告定位：基于 GitHub 源码仓库的系统性技术分析，为 Image_MultiModel 项目提供可借鉴特性参考

---

## 目录

1. [项目概览](#1-项目概览)
2. [核心技术栈](#2-核心技术栈)
3. [核心功能模块详解](#3-核心功能模块详解)
4. [可借鉴特性](#4-可借鉴特性)
5. [与 Image_MultiModel 的异同及移植建议](#5-与-image_multimodel-的异同及移植建议)
6. [总结与技术参考价值](#6-总结与技术参考价值)

---

## 1. 项目概览

Fooocus 是一个基于 Stable Diffusion XL 的图像生成软件，重新思考了图像生成器的设计理念。软件离线、开源、免费，类似于 Midjourney 等在线图像生成器，用户无需手动调整参数，只需专注于提示词和图像。Fooocus 简化了安装流程，从下载到生成第一张图像，鼠标点击次数严格限制在 3 次以内。最低 GPU 内存要求为 4GB（Nvidia）。

### 项目标识

| 属性 | 值 |
|------|-----|
| 项目名称 | Fooocus |
| 开发组织 | lllyasviel |
| 许可证 | GPL-3.0 |
| 主要语言 | Python |
| 一句话定位 | 简化的 Stable Diffusion XL 图像生成器，类似 Midjourney 的易用性 |

### 核心特性

- **极简安装**：3 次点击完成安装和首次生成
- **低门槛**：最低 4GB VRAM 即可运行
- **智能提示词处理**：内置 GPT-2 提示词扩展引擎
- **高质量输出**：自动优化采样参数，无需手动调优
- **多预设支持**：默认、动漫、写实等多种预设
- **丰富的功能**：文本到图像、图像到图像、修复、放大、ControlNet 等

### 当前状态

项目进入有限长期支持（LTS）状态，仅修复 bug，不再添加新功能或迁移到更新的模型架构。

---

## 2. 核心技术栈

| 层级 | 技术 | 职责 |
|------|------|------|
| **Web 框架** | Gradio | Web 界面 |
| **深度学习** | PyTorch | 模型推理 |
| **扩散模型** | ldm_patched (ComfyUI 分支) | SDXL 模型加载和采样 |
| **提示词扩展** | GPT-2 (transformers) | 智能提示词扩展 |
| **图像处理** | OpenCV + PIL | 图像预处理和后处理 |
| **修复模型** | 自训练 inpaint 模型 | 高质量修复 |

### 架构设计

Fooocus 采用分层架构：
- **UI 层**：Gradio 构建的 Web 界面
- **任务层**：异步任务队列处理生成请求
- **Pipeline 层**：模型加载、采样、后处理
- **模型层**：SDXL 基础模型 + Refiner + ControlNet + Inpaint

---

## 3. 核心功能模块详解

### 3.1 异步任务系统

**核心文件**：`modules/async_worker.py`

```python
class AsyncTask:
    def __init__(self, args):
        self.args = args.copy()
        self.yields = []
        self.results = []
        self.last_stop = False
        self.processing = False
        
        # 解析所有参数
        self.prompt = args.pop()
        self.negative_prompt = args.pop()
        self.style_selections = args.pop()
        self.performance_selection = Performance(args.pop())
        self.steps = self.performance_selection.steps()
        self.aspect_ratios_selection = args.pop()
        self.image_number = args.pop()
        self.seed = int(args.pop())
        # ... 更多参数
```

**任务流程**：
1. 接收用户输入（提示词、参数等）
2. 创建 AsyncTask 对象
3. 加入异步任务队列
4. 后台线程处理任务
5. 通过 yields 返回进度和结果

**关键特性**：
- 非阻塞任务处理
- 实时进度反馈
- 支持任务中断
- 结果自动排序

### 3.2 提示词扩展引擎

**核心文件**：`extras/expansion.py`

```python
class FooocusExpansion:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(path_fooocus_expansion)
        
        # 加载正向词表
        positive_words = open(os.path.join(path_fooocus_expansion, 'positive.txt'),
                              encoding='utf-8').read().splitlines()
        positive_words = ['Ġ' + x.lower() for x in positive_words if x != '']
        
        # 构建 logits 偏置
        self.logits_bias = torch.zeros((1, len(self.tokenizer.vocab)), 
                                       dtype=torch.float32) + neg_inf
        for k, v in self.tokenizer.vocab.items():
            if k in positive_words:
                self.logits_bias[0, v] = 0
        
        # 加载 GPT-2 模型
        self.model = AutoModelForCausalLM.from_pretrained(path_fooocus_expansion)
        self.model.eval()
```

**工作原理**：
- 使用 GPT-2 作为基础模型
- 通过 logits 偏置引导生成正向描述词
- 自动扩展简短提示词为详细描述
- 支持多语言提示词

**示例**：
```
输入："house in garden"
输出："a beautiful house in a lush garden with flowers, 
       architectural photography, high quality, detailed"
```

### 3.3 模型管理

**核心文件**：`modules/default_pipeline.py`

```python
model_base = core.StableDiffusionModel()
model_refiner = core.StableDiffusionModel()

@torch.no_grad()
@torch.inference_mode()
def refresh_base_model(name, vae_name=None):
    global model_base
    
    filename = get_file_from_folder_list(name, modules.config.paths_checkpoints)
    vae_filename = None
    if vae_name is not None and vae_name != modules.flags.default_vae:
        vae_filename = get_file_from_folder_list(vae_name, modules.config.path_vae)
    
    if model_base.filename == filename and model_base.vae_filename == vae_filename:
        return
    
    model_base = core.load_model(filename, vae_filename)
    print(f'Base model loaded: {model_base.filename}')
```

**模型类型**：
- **基础模型**：SDXL 1.0 及其变体
- **Refiner 模型**：SDXL Refiner
- **VAE**：可选的 VAE 模型
- **ControlNet**：各种控制模型
- **Inpaint 模型**：自训练的修复模型
- **LoRA**：低秩适应模型

**加载策略**：
- 懒加载：首次使用时加载
- 缓存机制：避免重复加载
- 自动卸载：不活跃模型移到 CPU

### 3.4 修复系统

**核心文件**：`modules/inpaint_worker.py`

```python
class InpaintHead(torch.nn.Module):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.head = torch.nn.Parameter(torch.empty(size=(320, 5, 3, 3), device='cpu'))
    
    def __call__(self, x):
        x = torch.nn.functional.pad(x, (1, 1, 1, 1), "replicate")
        return torch.nn.functional.conv2d(input=x, weight=self.head)

def morphological_open(x):
    """形态学开运算"""
    x_int16 = np.zeros_like(x, dtype=np.int16)
    x_int16[x > 127] = 256
    
    for i in range(32):
        maxed = max_filter_opencv(x_int16, ksize=3) - 8
        x_int16 = np.maximum(maxed, x_int16)
    
    x_uint8 = np.clip(x_int16, 0, 255).astype(np.uint8)
    return x_uint8
```

**修复功能**：
- **Inpaint**：局部修复
- **Outpaint**：向外扩展
- **Mask 生成**：SAM 自动分割
- **形态学处理**：优化 mask 边缘

**自训练模型**：
- Fooocus 使用自训练的 inpaint 模型
- 比标准 SDXL inpaint 效果更好
- 支持高质量修复和扩展

### 3.5 预设系统

**核心文件**：`presets/*.json`

```json
{
    "default_model": "juggernautXL_version6Rundiffusion.safetensors",
    "refiner_model": "sd_xl_refiner_1.0_0.9vae.safetensors",
    "refiner_switch": 0.5,
    "default_loras": [
        ["None", 1.0],
        ["None", 1.0],
        ["None", 1.0]
    ],
    "default_aspect_ratio": "1152*896",
    "checkpoint_downloads": {
        "juggernautXL_version6Rundiffusion.safetensors": "https://..."
    }
}
```

**预设类型**：
- **default**：通用预设
- **anime**：动漫风格
- **realistic**：写实风格
- **sai**：Stable Artistry
- **playground_v2.5**：Playground v2.5
- **pony_v6**：Pony v6
- **lcm**：LCM 快速生成

**预设功能**：
- 定义默认模型和参数
- 自动下载缺失模型
- 一键切换风格

### 3.6 配置系统

**核心文件**：`modules/config.py`

```python
config_path = get_config_path('config_path', "./config.txt")
config_dict = {}

# 加载默认预设
with open(os.path.abspath(f'./presets/default.json'), "r", encoding="utf-8") as json_file:
    config_dict.update(json.load(json_file))

# 加载用户配置
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as json_file:
        config_dict.update(json.load(json_file))
        always_save_keys = list(config_dict.keys())
```

**配置项**：
- 模型路径
- 默认参数
- 输出格式
- 性能设置
- UI 配置

**配置优先级**：
1. 环境变量
2. 用户配置文件
3. 预设文件
4. 默认值

### 3.7 样式系统

**核心文件**：`modules/sdxl_styles.py`

```python
legal_style_names = [
    "Fooocus V2",
    "Fooocus Enhance",
    "Fooocus Sharp",
    "Default (SXL)",
    "Anime",
    "Photographic",
    "Digital Art",
    "Comic Book",
    "Fantasy Art",
    "Analog Film",
    "Neon Punk",
    "Isometric",
    "Low Poly",
    "Origami",
    "Line Art",
    "Cinematic",
    "3D Model",
    "Pixel Art",
]
```

**样式功能**：
- 预定义的提示词模板
- 自动应用风格化参数
- 支持自定义样式
- 样式组合

---

## 4. 可借鉴特性

### 4.1 智能提示词扩展

**核心思想**：
- 使用 GPT-2 自动扩展简短提示词
- 通过 logits 偏置引导生成正向描述
- 降低用户提示词工程门槛

**实现方式**：
```python
# 用户输入
prompt = "a cat"

# Fooocus 扩展
expanded_prompt = expansion_model(prompt)
# 输出："a cute cat, detailed, high quality, professional photography"
```

**优势**：
- 降低使用门槛
- 提高生成质量
- 减少提示词工程时间

**对 Image_MultiModel 的启发**：
- 集成类似的提示词扩展功能
- 使用 LLM 优化提示词
- 提供提示词模板和建议

### 4.2 预设系统

**设计模式**：
- JSON 配置文件定义预设
- 包含模型、参数、LoRA 等配置
- 自动下载缺失模型
- 一键切换预设

**实现细节**：
```python
# 预设加载
def load_preset(preset_name):
    preset_path = f"presets/{preset_name}.json"
    with open(preset_path) as f:
        preset = json.load(f)
    
    # 应用预设配置
    config.default_model = preset['default_model']
    config.refiner_switch = preset['refiner_switch']
    config.default_loras = preset['default_loras']
    
    # 下载缺失模型
    for model, url in preset['checkpoint_downloads'].items():
        if not os.path.exists(model):
            download_model(url, model)
```

**应用价值**：
- 快速切换风格
- 降低配置复杂度
- 提供最佳实践

### 4.3 极简安装流程

**安装策略**：
- 一键安装包（Windows）
- 自动下载模型
- 最小化依赖
- 离线可用

**安装步骤**：
1. 下载 7z 压缩包
2. 解压到任意目录
3. 运行 `run.bat`
4. 自动下载模型并启动

**优势**：
- 3 次点击完成安装
- 无需 Python 环境
- 便携性强
- 适合新手用户

### 4.4 低显存优化

**优化策略**：
- 最低 4GB VRAM 支持
- 使用虚拟内存（Windows 页面文件）
- 模型卸载到 CPU
- 分块处理大图像

**实现方式**：
```python
# 检测 VRAM
total_vram = torch.cuda.get_device_properties(0).total_memory

if total_vram < 4 * 1024**3:
    # 启用低显存模式
    enable_model_offload()
    enable_cpu_offload()
    enable_tiled_vae()
```

**应用效果**：
- 支持笔记本 GPU（3060 Laptop）
- 扩大用户群体
- 提高可访问性

### 4.5 自训练 Inpaint 模型

**技术亮点**：
- 自训练的 inpaint 模型
- 比标准 SDXL inpaint 效果更好
- 支持高质量修复和扩展

**模型特点**：
- 专门针对 SDXL 优化
- 支持大区域修复
- 保持图像一致性
- 自然的边缘过渡

**应用价值**：
- 提高修复质量
- 减少伪影
- 提升用户体验

### 4.6 异步任务队列

**设计模式**：
```python
async_tasks = []

def worker_thread():
    while True:
        if len(async_tasks) > 0:
            task = async_tasks.pop(0)
            process_task(task)
        else:
            time.sleep(0.01)

def process_task(task):
    task.processing = True
    
    # 执行生成
    for step in range(task.steps):
        # 生成步骤
        result = generate_step(task, step)
        
        # 返回进度
        task.yields.append(('preview', (step / task.steps, f'Step {step}', result)))
    
    # 返回结果
    task.yields.append(('results', final_images))
    task.yields.append(('finish', None))
    task.processing = False
```

**优势**：
- 非阻塞 UI
- 实时进度反馈
- 支持任务取消
- 结果自动排序

---

## 5. 与 Image_MultiModel 的异同及移植建议

### 5.1 技术相似性

| 方面 | Fooocus | Image_MultiModel |
|------|---------|------------------|
| **核心功能** | 图像生成 | 图像生成 |
| **技术栈** | Python + PyTorch | Python + PyTorch |
| **Web 框架** | Gradio | FastAPI + Gradio |
| **模型支持** | SDXL | SD/SDXL/Flux |
| **目标用户** | 普通用户 | 普通用户 |

### 5.2 差异分析

**Fooocus 的特点**：
- 极简设计：专注于 SDXL
- 智能扩展：GPT-2 提示词扩展
- 低门槛：4GB VRAM 即可运行
- 预设系统：多种风格预设

**Image_MultiModel 的特点**：
- 多模型支持：SD/SDXL/Flux 等多引擎
- 多引擎架构：ComfyUI/原生引擎切换
- 中文优化：针对中文用户优化
- 一键部署：便携版支持

### 5.3 可移植特性

#### 特征 1：智能提示词扩展

**移植价值**：
- 降低用户提示词工程门槛
- 提高生成质量
- 改善用户体验

**实现建议**：
```python
# 在 Image_MultiModel 中集成提示词扩展
from transformers import AutoTokenizer, AutoModelForCausalLM

class PromptExpander:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained('gpt2')
        self.model = AutoModelForCausalLM.from_pretrained('gpt2')
    
    def expand(self, prompt):
        """扩展提示词"""
        inputs = self.tokenizer(prompt, return_tensors='pt')
        outputs = self.model.generate(
            inputs.input_ids,
            max_length=100,
            num_return_sequences=1,
            logits_bias=self.positive_bias
        )
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)
```

#### 特征 2：预设系统

**应用场景**：
- 快速切换风格
- 提供最佳实践
- 降低配置复杂度

**实现方案**：
```python
# 预设配置文件 presets/anime.json
{
    "name": "Anime",
    "base_model": "anima-pen-xl-v1.0.safetensors",
    "refiner_model": "None",
    "loras": [
        ["anime_style.safetensors", 0.8]
    ],
    "default_prompt": "anime style, high quality, detailed",
    "default_negative": "low quality, blurry"
}

# 预设加载
def apply_preset(preset_name):
    preset = load_preset(preset_name)
    config.base_model = preset['base_model']
    config.loras = preset['loras']
    # ... 应用其他配置
```

#### 特征 3：低显存优化

**应用价值**：
- 支持更多用户
- 提高可访问性
- 扩大用户群体

**技术要点**：
- 模型卸载到 CPU
- 分块 VAE 处理
- 使用虚拟内存
- 优化内存管理

#### 特征 4：异步任务系统

**应用方向**：
- 非阻塞 UI
- 实时进度反馈
- 支持批量生成

**实现方式**：
```python
# 异步任务队列
class TaskQueue:
    def __init__(self):
        self.tasks = []
        self.current_task = None
    
    def submit(self, task):
        self.tasks.append(task)
    
    def process_loop(self):
        while True:
            if len(self.tasks) > 0:
                self.current_task = self.tasks.pop(0)
                self.current_task.processing = True
                
                # 执行生成
                for step in range(self.current_task.steps):
                    result = self.generate_step(step)
                    self.current_task.yields.append(('preview', result))
                
                self.current_task.yields.append(('finish', None))
                self.current_task.processing = False
            else:
                time.sleep(0.01)
```

#### 特征 5：自训练 Inpaint 模型

**应用价值**：
- 提高修复质量
- 减少伪影
- 提升用户体验

**集成方案**：
- 训练专门的 inpaint 模型
- 集成到 Image_MultiModel
- 提供高质量修复功能

### 5.4 集成架构建议

```
Image_MultiModel 增强架构（借鉴 Fooocus）：

┌─────────────────────────────────────┐
│         用户界面层                    │
│      (Gradio + 实时进度)             │
└──────────────┬──────────────────────┘
               │
               ├─► 提示词扩展器
               │    ├─ GPT-2 扩展
               │    ├─ 正向词表引导
               │    └─ 多语言支持
               │
               ├─► 预设管理器
               │    ├─ 预设加载
               │    ├─ 自动下载
               │    └─ 一键切换
               │
               ├─► 任务队列
               │    ├─ 异步处理
               │    ├─ 进度反馈
               │    └─ 任务取消
               │
               ├─► 内存管理器
               │    ├─ VRAM 检测
               │    ├─ 模型卸载
               │    └─ 低显存优化
               │
               └─► 修复引擎
                    ├─ 自训练模型
                    ├─ Mask 生成
                    └─ 高质量修复
```

---

## 6. 总结与技术参考价值

### 6.1 核心价值

1. **极简设计**：降低使用门槛，专注核心功能
2. **智能扩展**：GPT-2 提示词扩展提高生成质量
3. **低门槛**：4GB VRAM 即可运行
4. **预设系统**：快速切换风格，提供最佳实践
5. **高质量修复**：自训练 inpaint 模型

### 6.2 对 Image_MultiModel 的技术贡献

| 技术领域 | 贡献 | 优先级 |
|---------|------|--------|
| **提示词扩展** | 智能提示词扩展降低门槛 | 高 |
| **预设系统** | 快速切换风格和配置 | 高 |
| **低显存优化** | 支持更多用户 | 中 |
| **异步任务** | 非阻塞 UI 和实时反馈 | 中 |
| **修复质量** | 自训练高质量修复模型 | 低 |

### 6.3 实施建议

**短期目标**（1-2 周）：
- 集成提示词扩展功能
- 实现预设系统
- 优化低显存支持

**中期目标**（1 个月）：
- 完善异步任务系统
- 训练自训练 inpaint 模型
- 提供更多预设

**长期目标**（3 个月）：
- 构建预设社区
- 开发更多智能辅助功能
- 优化用户体验

### 6.4 技术风险与注意事项

1. **GPT-2 依赖**：提示词扩展需要额外的 GPT-2 模型
2. **预设维护**：需要持续维护和更新预设
3. **模型训练**：自训练 inpaint 模型需要数据和算力
4. **兼容性**：确保与现有代码的兼容性

### 6.5 参考资源

- **官方仓库**：https://github.com/lllyasviel/Fooocus
- **模型下载**：https://huggingface.co/lllyasviel/fooocus
- **预设集合**：https://github.com/lllyasviel/Fooocus/discussions/679
- **相关项目**：https://github.com/lllyasviel/stable-diffusion-webui-forge

---

**报告编制**：Image_MultiModel 技术分析团队  
**最后更新**：2026-08-13  
**版本**：v1.0
