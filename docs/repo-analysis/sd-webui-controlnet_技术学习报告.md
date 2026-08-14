# sd-webui-controlnet 开源仓库技术分析报告

> 仓库地址：https://github.com/Mikubill/sd-webui-controlnet
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

sd-webui-controlnet 是 AUTOMATIC1111 Stable Diffusion WebUI 的 ControlNet 扩展插件，允许在 WebUI 中添加 ControlNet 和其他注入式 SD 控制机制。该扩展支持所有 ControlNet 1.0/1.1 和 T2I-Adapter 模型，提供像素级精确控制、多种控制模式、参考图像控制等高级功能。

### 项目标识

| 属性 | 值 |
|------|-----|
| 项目名称 | sd-webui-controlnet |
| 开发组织 | Mikubill |
| 许可证 | Apache-2.0 |
| 主要语言 | Python |
| 一句话定位 | Stable Diffusion WebUI 的 ControlNet 扩展，支持多种控制模型和预处理器 |

### 核心特性

- **完整模型支持**：支持所有 ControlNet 1.0/1.1 和 T2I-Adapter 模型
- **高分辨率修复**：完美支持 A1111 High-Res Fix
- **修复和重绘**：支持所有 img2img 和 inpaint 设置
- **像素完美模式**：自动计算最佳预处理器分辨率
- **多种控制模式**：平衡、提示词优先、ControlNet 优先
- **参考图像控制**：无需控制模型即可使用参考图像
- **用户友好界面**：重新组织的 UI 和预处理器预览
- **放大支持**：支持几乎所有放大脚本

### 当前状态

项目活跃开发中，最新版本 v1.1.454（2024年7月），支持 ControlNet Union 模型和最新预处理器。

---

## 2. 核心技术栈

| 层级 | 技术 | 职责 |
|------|------|------|
| **Web 框架** | Gradio | Web 界面（基于 A1111） |
| **深度学习** | PyTorch | 模型推理 |
| **ControlNet** | 自实现 + 官方模型 | 条件控制 |
| **预处理器** | OpenCV + 自定义模型 | 图像预处理 |
| **API** | FastAPI | REST API 扩展 |
| **图像处理** | PIL + OpenCV | 图像变换 |

### 架构设计

sd-webui-controlnet 采用插件架构：
- **扩展层**：A1111 扩展接口
- **控制层**：ControlNet 注入和管理
- **预处理层**：图像预处理和特征提取
- **API 层**：REST API 扩展

---

## 3. 核心功能模块详解

### 3.1 ControlNet 集成

**核心文件**：`scripts/external_code.py`

```python
class ControlNetUnit:
    def __init__(
        self,
        enabled: bool = True,
        module: str = "none",
        model: str = "None",
        weight: float = 1.0,
        image: Union[Image.Image, np.ndarray, str] = None,
        resize_mode: str = "Crop and Resize",
        lowvram: bool = False,
        processor_res: int = -1,
        threshold_a: float = -1,
        threshold_b: float = -1,
        guidance_start: float = 0.0,
        guidance_end: float = 1.0,
        control_mode: int = 0,
        pixel_perfect: bool = False,
    ):
        self.enabled = enabled
        self.module = module
        self.model = model
        self.weight = weight
        self.image = image
        self.resize_mode = resize_mode
        self.lowvram = lowvram
        self.processor_res = processor_res
        self.threshold_a = threshold_a
        self.threshold_b = threshold_b
        self.guidance_start = guidance_start
        self.guidance_end = guidance_end
        self.control_mode = control_mode
        self.pixel_perfect = pixel_perfect
```

**ControlNet 注入机制**：
```python
def apply_controlnet(model, controlnet, control_image, weight, guidance_start, guidance_end):
    """应用 ControlNet 到模型"""
    # 1. 预处理控制图像
    control_latent = preprocess(control_image)
    
    # 2. 注入 ControlNet
    def controlnet_forward(x, t, cond):
        # 运行 ControlNet
        control = controlnet(control_latent, t, cond)
        
        # 应用权重和时间范围
        if t < guidance_start or t > guidance_end:
            return 0
        
        return control * weight
    
    # 3. 修改 UNet 前向传播
    model.original_forward = model.forward
    model.forward = lambda x, t, cond: (
        model.original_forward(x, t, cond) + controlnet_forward(x, t, cond)
    )
```

### 3.2 预处理器系统

**核心文件**：`annotator/`

```python
class Preprocessor:
    """预处理器基类"""
    def __init__(self, name):
        self.name = name
    
    def __call__(self, image, resolution):
        """执行预处理"""
        raise NotImplementedError

class CannyPreprocessor(Preprocessor):
    """Canny 边缘检测"""
    def __init__(self):
        super().__init__("canny")
    
    def __call__(self, image, resolution=512):
        # 调整大小
        image = resize_image(image, resolution)
        
        # Canny 边缘检测
        edges = cv2.Canny(image, 100, 200)
        
        return edges

class DepthPreprocessor(Preprocessor):
    """深度估计（MiDaS）"""
    def __init__(self):
        super().__init__("depth_midas")
        self.model = load_midas_model()
    
    def __call__(self, image, resolution=512):
        image = resize_image(image, resolution)
        depth = self.model(image)
        return depth
```

**支持的预处理器**：
- **边缘检测**：Canny、HED、PiDiNet、M-LSD
- **深度估计**：MiDaS、Zoe、Depth Anything
- **法线图**：Normal BAE、Normal Midas
- **姿态估计**：OpenPose、AnimalPose
- **语义分割**：Segmentation
- **线条检测**：Lineart、Anime Lineart
- **涂鸦**：Scribble
- **参考**：Reference-only、IP-Adapter

### 3.3 控制模式

**核心文件**：`scripts/external_code.py`

```python
class ControlMode(IntEnum):
    BALANCED = 0        # 平衡模式
    PROMPT_IMPORTANCE = 1  # 提示词优先
    CONTROLNET_IMPORTANCE = 2  # ControlNet 优先

def apply_control_mode(control, mode, cfg_scale):
    """应用控制模式"""
    if mode == ControlMode.BALANCED:
        # 在 CFG 的两侧都应用 ControlNet
        return control, control
    
    elif mode == ControlMode.PROMPT_IMPORTANCE:
        # 提示词优先：逐渐减少 ControlNet 注入
        # layer_weight *= 0.825^I
        return control * 0.825, control * 0.825
    
    elif mode == ControlMode.CONTROLNET_IMPORTANCE:
        # ControlNet 优先：仅在条件侧应用
        # ControlNet 强度 = cfg_scale 倍
        return control * cfg_scale, 0
```

**控制模式说明**：
- **平衡**：ControlNet 在 CFG 两侧，标准模式
- **提示词优先**：减少 ControlNet 影响，保留更多提示词语义
- **ControlNet 优先**：增强 ControlNet 影响，更精确控制结构

### 3.4 像素完美模式

**核心文件**：`scripts/preprocessor.py`

```python
def detect_resolution(image, target_size):
    """检测最佳预处理器分辨率"""
    H, W = image.shape[:2]
    
    # 计算缩放比例
    scale = target_size / max(H, W)
    
    # 计算新尺寸（8 的倍数）
    new_H = int(H * scale) // 8 * 8
    new_W = int(W * scale) // 8 * 8
    
    return new_H, new_W

def pixel_perfect_preprocess(image, model, target_size):
    """像素完美预处理"""
    # 1. 检测最佳分辨率
    H, W = detect_resolution(image, target_size)
    
    # 2. 调整图像大小
    image = cv2.resize(image, (W, H))
    
    # 3. 应用预处理器
    control_image = model(image, resolution=max(H, W))
    
    return control_image
```

**优势**：
- 自动计算最佳分辨率
- 确保像素对齐
- 减少伪影和失真

### 3.5 参考图像控制

**核心文件**：`scripts/preprocessor/reference.py`

```python
class ReferenceOnlyPreprocessor:
    """参考图像控制（无需控制模型）"""
    def __init__(self):
        self.name = "reference-only"
    
    def __call__(self, image, model):
        """使用参考图像引导生成"""
        # 1. 编码参考图像
        ref_latent = model.vae.encode(image)
        
        # 2. 注入到注意力层
        def attention_injection(attention_layer):
            # 将参考图像的特征注入到注意力
            original_forward = attention_layer.forward
            
            def injected_forward(q, k, v):
                # 添加参考图像的键值对
                k_ref = model.vae.encode(ref_latent)
                v_ref = model.vae.encode(ref_latent)
                
                k = torch.cat([k, k_ref], dim=1)
                v = torch.cat([v, v_ref], dim=1)
                
                return original_forward(q, k, v)
            
            attention_layer.forward = injected_forward
        
        return attention_injection
```

**工作原理**：
- 直接连接注意力层
- 使用参考图像作为键值对
- 无需额外的控制模型
- 保持图像风格一致性

### 3.6 API 扩展

**核心文件**：`scripts/api.py`

```python
def controlnet_api(_: gr.Blocks, app: FastAPI):
    """ControlNet API 扩展"""
    
    @app.get("/controlnet/version")
    async def version():
        """获取 API 版本"""
        return {"version": "1.1.454"}
    
    @app.get("/controlnet/model_list")
    async def model_list():
        """获取可用模型列表"""
        models = get_controlnet_models()
        return {"model_list": models}
    
    @app.get("/controlnet/module_list")
    async def module_list():
        """获取可用预处理器列表"""
        modules = get_preprocessor_list()
        return {"module_list": modules}
    
    @app.post("/controlnet/detect")
    async def detect(
        controlnet_module: str = Body("none"),
        controlnet_input_images: List[str] = Body([]),
        controlnet_processor_res: int = Body(512),
    ):
        """执行预处理"""
        results = []
        for image in controlnet_input_images:
            image = decode_base64(image)
            preprocessor = get_preprocessor(controlnet_module)
            result = preprocessor(image, controlnet_processor_res)
            results.append(encode_base64(result))
        
        return {"images": results}
```

**API 端点**：
- `/controlnet/version`：API 版本
- `/controlnet/model_list`：模型列表
- `/controlnet/module_list`：预处理器列表
- `/controlnet/detect`：执行预处理

---

## 4. 可借鉴特性

### 4.1 插件化架构

**核心思想**：
- 作为 A1111 的扩展插件
- 不修改核心代码
- 通过钩子和回调集成

**设计模式**：
```python
class ControlNetExtension(scripts.Script):
    def __init__(self):
        self.name = "ControlNet"
    
    def ui(self, is_img2img):
        """创建 UI"""
        with gr.Accordion("ControlNet", open=False):
            enabled = gr.Checkbox(label="Enable", value=False)
            module = gr.Dropdown(choices=get_module_list(), label="Preprocessor")
            model = gr.Dropdown(choices=get_model_list(), label="Model")
            weight = gr.Slider(minimum=0, maximum=2, value=1, label="Weight")
            # ... 更多控件
        
        return [enabled, module, model, weight, ...]
    
    def run(self, p, *args):
        """执行生成"""
        # 解析参数
        unit = ControlNetUnit(*args)
        
        if not unit.enabled:
            return
        
        # 加载 ControlNet
        controlnet = load_controlnet(unit.model)
        
        # 预处理图像
        control_image = preprocess(unit.image, unit.module)
        
        # 注入 ControlNet
        apply_controlnet(p.sd_model, controlnet, control_image, unit.weight)
        
        # 执行生成
        return processing.process_images(p)
```

**优势**：
- 模块化设计
- 易于维护和更新
- 不侵入核心代码

**对 Image_MultiModel 的启发**：
- 采用插件化架构
- 支持扩展功能
- 保持核心代码稳定

### 4.2 预处理器系统

**设计模式**：
```python
class PreprocessorRegistry:
    """预处理器注册表"""
    def __init__(self):
        self.preprocessors = {}
    
    def register(self, name, preprocessor_class):
        """注册预处理器"""
        self.preprocessors[name] = preprocessor_class
    
    def get(self, name):
        """获取预处理器"""
        return self.preprocessors[name]

# 注册预处理器
registry = PreprocessorRegistry()
registry.register("canny", CannyPreprocessor)
registry.register("depth_midas", DepthPreprocessor)
registry.register("openpose", OpenPosePreprocessor)
```

**优势**：
- 易于添加新预处理器
- 统一的接口
- 动态加载

### 4.3 控制模式

**核心思想**：
- 提供不同的控制强度策略
- 平衡提示词和 ControlNet 的影响
- 用户可根据需求选择

**实现方式**：
```python
def apply_control_mode(control, mode, cfg_scale):
    """应用控制模式"""
    if mode == "balanced":
        # 标准模式
        return control, control
    
    elif mode == "prompt_priority":
        # 提示词优先：减少 ControlNet 影响
        decay = 0.825 ** layer_index
        return control * decay, control * decay
    
    elif mode == "controlnet_priority":
        # ControlNet 优先：仅在条件侧应用
        return control * cfg_scale, 0
```

**应用价值**：
- 灵活控制生成过程
- 适应不同场景需求
- 提升用户体验

### 4.4 像素完美模式

**核心思想**：
- 自动计算最佳预处理器分辨率
- 确保像素对齐
- 减少伪影

**实现细节**：
```python
def pixel_perfect_resize(image, target_size):
    """像素完美调整大小"""
    H, W = image.shape[:2]
    
    # 计算缩放比例
    scale = target_size / max(H, W)
    
    # 计算新尺寸（8 的倍数）
    new_H = int(H * scale) // 8 * 8
    new_W = int(W * scale) // 8 * 8
    
    return new_H, new_W
```

**优势**：
- 自动化处理
- 提高生成质量
- 减少手动调整

### 4.5 参考图像控制

**创新点**：
- 无需控制模型
- 直接连接注意力层
- 保持风格一致性

**应用场景**：
- 风格迁移
- 角色一致性
- 图像变体生成

**技术实现**：
```python
def reference_only_control(ref_image, model):
    """参考图像控制"""
    # 编码参考图像
    ref_latent = model.vae.encode(ref_image)
    
    # 注入到注意力层
    def inject_attention(attention):
        original_forward = attention.forward
        
        def injected_forward(q, k, v):
            # 添加参考图像的键值对
            k_ref = encode(ref_latent)
            v_ref = encode(ref_latent)
            
            k = torch.cat([k, k_ref], dim=1)
            v = torch.cat([v, v_ref], dim=1)
            
            return original_forward(q, k, v)
        
        attention.forward = injected_forward
```

---

## 5. 与 Image_MultiModel 的异同及移植建议

### 5.1 技术相似性

| 方面 | sd-webui-controlnet | Image_MultiModel |
|------|---------------------|------------------|
| **核心功能** | ControlNet 控制 | 图像生成 |
| **技术栈** | Python + PyTorch | Python + PyTorch |
| **Web 框架** | Gradio (A1111) | FastAPI + Gradio |
| **扩展性** | 插件架构 | 多引擎架构 |

### 5.2 差异分析

**sd-webui-controlnet 的特点**：
- 专注于 ControlNet 控制
- 插件化架构
- 丰富的预处理器
- 多种控制模式

**Image_MultiModel 的特点**：
- 多模型支持
- 多引擎架构
- 一键部署
- 用户友好界面

### 5.3 可移植特性

#### 特征 1：预处理器系统

**移植价值**：
- 提供丰富的图像预处理能力
- 支持多种控制条件
- 提升生成控制精度

**实现建议**：
```python
# 在 Image_MultiModel 中实现预处理器系统
class PreprocessorRegistry:
    def __init__(self):
        self.preprocessors = {}
    
    def register(self, name, preprocessor):
        self.preprocessors[name] = preprocessor
    
    def get(self, name):
        return self.preprocessors[name]

# 注册预处理器
registry = PreprocessorRegistry()
registry.register("canny", CannyPreprocessor())
registry.register("depth", DepthPreprocessor())
registry.register("openpose", OpenPosePreprocessor())
```

#### 特征 2：控制模式

**应用场景**：
- 灵活控制生成过程
- 平衡提示词和控制条件
- 适应不同需求

**实现方案**：
```python
class ControlMode:
    BALANCED = "balanced"
    PROMPT_PRIORITY = "prompt_priority"
    CONTROL_PRIORITY = "control_priority"

def apply_control_mode(control, mode, cfg_scale):
    if mode == ControlMode.BALANCED:
        return control, control
    elif mode == ControlMode.PROMPT_PRIORITY:
        return control * 0.8, control * 0.8
    elif mode == ControlMode.CONTROL_PRIORITY:
        return control * cfg_scale, 0
```

#### 特征 3：像素完美模式

**应用价值**：
- 自动计算最佳分辨率
- 减少伪影
- 提高生成质量

**技术要点**：
- 检测目标分辨率
- 计算缩放比例
- 确保 8 的倍数对齐

#### 特征 4：参考图像控制

**应用方向**：
- 风格迁移
- 角色一致性
- 图像变体

**实现方式**：
```python
def reference_control(ref_image, model):
    """参考图像控制"""
    # 编码参考图像
    ref_latent = model.vae.encode(ref_image)
    
    # 注入到注意力层
    def inject_attention(attention):
        original_forward = attention.forward
        
        def injected_forward(q, k, v):
            k_ref = encode(ref_latent)
            v_ref = encode(ref_latent)
            
            k = torch.cat([k, k_ref], dim=1)
            v = torch.cat([v, v_ref], dim=1)
            
            return original_forward(q, k, v)
        
        attention.forward = injected_forward
```

#### 特征 5：API 扩展

**应用价值**：
- 提供 REST API
- 支持自动化脚本
- 集成到其他系统

**集成方案**：
```python
@app.get("/controlnet/models")
async def get_models():
    """获取 ControlNet 模型列表"""
    return {"models": list_models()}

@app.post("/controlnet/preprocess")
async def preprocess(image: str, module: str):
    """执行预处理"""
    preprocessor = get_preprocessor(module)
    result = preprocessor(decode_image(image))
    return {"image": encode_image(result)}
```

### 5.4 集成架构建议

```
Image_MultiModel 增强架构（借鉴 sd-webui-controlnet）：

┌─────────────────────────────────────┐
│         用户界面层                    │
│      (Gradio + ControlNet UI)        │
└──────────────┬──────────────────────┘
               │
               ├─► 预处理器系统
               │    ├─ 边缘检测（Canny/HED）
               │    ├─ 深度估计（MiDaS/Depth Anything）
               │    ├─ 姿态估计（OpenPose）
               │    └─ 语义分割
               │
               ├─► ControlNet 管理器
               │    ├─ 模型加载
               │    ├─ 权重控制
               │    └─ 时间范围
               │
               ├─► 控制模式
               │    ├─ 平衡模式
               │    ├─ 提示词优先
               │    └─ ControlNet 优先
               │
               ├─► 像素完美模式
               │    ├─ 自动分辨率
               │    └─ 像素对齐
               │
               └─► 参考图像控制
                    ├─ 注意力注入
                    └─ 风格一致性
```

---

## 6. 总结与技术参考价值

### 6.1 核心价值

1. **完整 ControlNet 支持**：所有模型和预处理器
2. **灵活控制**：多种控制模式和策略
3. **像素完美**：自动优化分辨率
4. **参考控制**：无需模型的风格控制
5. **插件架构**：模块化设计

### 6.2 对 Image_MultiModel 的技术贡献

| 技术领域 | 贡献 | 优先级 |
|---------|------|--------|
| **预处理器系统** | 丰富的图像预处理能力 | 高 |
| **控制模式** | 灵活的生成控制策略 | 高 |
| **像素完美** | 自动优化生成质量 | 中 |
| **参考控制** | 无模型风格控制 | 中 |
| **API 扩展** | REST API 支持 | 低 |

### 6.3 实施建议

**短期目标**（1-2 周）：
- 实现预处理器注册表
- 集成基础预处理器（Canny、Depth）
- 实现控制模式

**中期目标**（1 个月）：
- 添加更多预处理器
- 实现像素完美模式
- 实现参考图像控制

**长期目标**（3 个月）：
- 构建完整的 ControlNet 系统
- 提供 API 扩展
- 支持自定义预处理器

### 6.4 技术风险与注意事项

1. **模型依赖**：需要下载 ControlNet 模型
2. **计算开销**：预处理器增加计算时间
3. **内存占用**：多个 ControlNet 同时使用需要更多内存
4. **兼容性**：确保与不同模型的兼容性

### 6.5 参考资源

- **官方仓库**：https://github.com/Mikubill/sd-webui-controlnet
- **ControlNet 论文**：https://arxiv.org/abs/2302.05543
- **模型下载**：https://huggingface.co/lllyasviel/ControlNet
- **A1111 WebUI**：https://github.com/AUTOMATIC1111/stable-diffusion-webui

---

**报告编制**：Image_MultiModel 技术分析团队  
**最后更新**：2026-08-13  
**版本**：v1.0
