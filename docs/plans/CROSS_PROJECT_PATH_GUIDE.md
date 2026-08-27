# 📁 多项目路径配置统一指南
# ================================================================================
# 
# 本文档为五个 AI 项目（Image_MultiModel, TTS_MultiModel, Seedvr2, SpiritPal, DraftPeek）
# 提供统一的路径配置策略和最佳实践。
#
# 🎯 核心理念：零配置启动 + 高级用户可定制
#
# ================================================================================

## 🚀 快速开始（新手必看）
#
# **好消息：所有项目现在都支持开箱即用！**
#
# 无论是哪个项目，您都可以：
# ✅ Clone 或下载后直接使用
# ✅ 无需修改任何配置文件  
# ✅ 整个项目可以打包分享给他人
#
# 详细配置方法见各项目的独立文档。
#
# ---

## 📊 五项目路径配置对比表
#
# | 项目 | 默认模式 | 环境<br>变量 | 可移植性 | 文档<br>完整性 | 备注 |
# |------|---------|------------|----------|--------------|------|
# | **Image_MultiModel** | ✅ portable | ✅ 完整 | ⭐⭐⭐⭐⭐ | ✅ 优秀 | v1.2.3 起改进 |
# | **TTS_MultiModel** | ✅ portable | ✅ 完整 | ⭐⭐⭐⭐⭐ | ✅ 优秀 | 已优化完成 |
# | **Seedvr2** | ✅ portable | ✅ 完整 | ⭐⭐⭐⭐⭐ | ✅ 良好 | 已有 path_guard |
# | **SpiritPal** | ✅ Tauri | ✅ 基础 | ⭐⭐⭐⭐ | ✅ 良好 | 桌面应用特殊处理 |
# | **DraftPeek** | N/A | - | ⭐⭐⭐⭐ | 🟡 Android | Android 项目不适用此方案 |
#
---

# 🏗️ 统一设计模式
#
# ### 1. 便携模式（Portable Mode） - 默认推荐
#
# 所有模型文件存储在项目的 `pretrained_models/` 目录：
#
# ```bash
# Project/
# ├── pretrained_models/       # 所有 AI 模型存放这里
# │   ├── VoxCPM2/            # 语音模型
# │   ├── IndexTTS2/          # TTS 模型
# │   └── text_encoders/      # 文本编码器
# ├── config.yaml             # 配置文件（使用相对路径）
# ├── .env.example           # 环境变量模板
# └── README.md              # 包含路径配置说明
# ```
#
# **优点**:
# - ✅ 零配置，clone 即可运行
# - ✅ 可离线使用
# - ✅ 方便分享（整个文件夹压缩即可）
# - ✅ 跨平台兼容
#
# **缺点**:
# - ⚠️ 每个项目都有完整的模型副本，占用更多磁盘空间
#
# ---
#
# ### 2. 共享模式（Shared Mode） - 节省空间的高级用法
#
# 多个 AI 项目共用一个模型目录：
#
# ```bash
# D:/AI_Shared_Models/              # 或 ~/AIModels / /opt/ai-models
# ├── VoxCPM2/                      # Image & TTS 项目共用
# ├── IndexTTS2/                    # TTS 项目专用
# ├── Z_image_turbo/                # Image 项目专用
# └── SenseVoiceSmall/              # ASR 模型
# ```
#
# **配置方式**（以 Image_MultiModel 为例）:
#
# 1. 复制 `.env.example` 为 `.env`
#
# 2. 编辑 `.env` 文件：
#    ```env
#    IMAGE_MODEL_MODE=shared
#    COMFY_MODELS_ROOT=D:/AI_Shared_Models
#    ```
#
# 3. 其他项目类似：
#    ```env
#    # TTS_MultiModel
#    TTS_MODEL_MODE=shared
#    TTS_SHARED_MODELS_ROOT=D:/AI_Shared_Models
#    
#    # Seedvr2  
#    SEEDVR_MODEL_MODE=shared
#    SEEDVR_SHARED_MODELS_ROOT=D:/AI_Shared_Models
#    ```
#
# **优点**:
# - ✅ 节省磁盘空间（多项目共用一份模型）
# - ✅ 统一管理，便于备份
# - ✅ 更新模型只需更新一次
#
# **缺点**:
# - ⚠️ 需要手动配置环境变量
# - ⚠️ 不方便直接分享给他人
#
# ---

## 🔧 各项目的具体实现
#
# ### Image_MultiModel (图像生成)
#
# **配置文件**: `config.yaml`
#
# **环境变量**:
# ```env
# IMAGE_MODEL_MODE=portable          # 或 shared
# COMFY_MODELS_ROOT=/path/to/models  # 仅 shared 模式使用
# LOG_LEVEL=INFO
# LOG_PATH=logs/app.log
# ```
#
# **文档**: [docs/PATH-CONFIGURATION.md](Image_MultiModel/docs/PATH-CONFIGURATION.md)
#
# ---
#
# ### TTS_MultiModel (语音合成)
#
# **配置文件**: `config.yaml`
#
# **环境变量**:
# ```env
# TTS_MODEL_MODE=portable            # 或 shared
# TTS_SHARED_MODELS_ROOT=/path/to/models
# ENVIRONMENT=development
# LOG_LEVEL=INFO
# LOG_PATH=logs/app.log
# ```
#
# **文档**: [docs/PATH-CONFIGURATION.md](TTS_MultiModel/docs/PATH-CONFIGURATION.md) *TODO: 待创建*
#
# ---
#
# ### Seedvr2 (视频超分)
#
# **配置文件**: `config.yaml`
#
# **环境变量**:
# ```env
# SEEDVR_MODEL_MODE=portable         # 或 shared
# SEEDVR_SHARED_MODELS_ROOT=/path/to/models
# LOG_LEVEL=INFO
# LOG_PATH=logs/app.log
# ```
#
# **特性**: 内置 PathGuard 路径安全防护机制
#
# **文档**: [docs/PATH-CONFIGURATION.md](Seedvr2/docs/PATH-CONFIGURATION.md) *TODO: 待创建*
#
# ---
#
# ### SpiritPal (桌面宠物)
#
# **架构**: Tauri 桌面应用（前端 TypeScript + 后端 Rust）
#
# **路径管理方式**:
# - 前端资源：相对路径（相对于 `src/` 目录）
# - 数据存储：使用操作系统 API 获取用户数据目录
#   - Windows: `%APPDATA%/spiritpal`
#   - macOS: `~/Library/Application Support/spiritpal`
#   - Linux: `~/.local/share/spiritpal`
#
# **环境变量**:
# ```env
# RUST_LOG=info
# TAURI_ENV_DEBUG=false
# OPENAI_API_KEY=sk-xxx  # 可选，API 密钥
# ```
#
# **特性**: 使用系统钥匙链安全存储敏感信息
#
# ---
#
# ### DraftPeek (代码编辑器 - Android)
#
# **架构**: Android 原生应用（Kotlin）
#
# **路径管理方式**:
# - 内部存储：`context.filesDir` (应用私有目录)
# - 外部存储：`ContextCompat.getExternalFilesDir()` (需权限)
# - 内容提供者：通过 URI 访问共享文件
#
# **注意**: Android 应用的沙箱机制自动处理路径隔离，无需手动配置。
#
# ---

## 💡 常见问题 FAQ
#
# **Q1: 我应该选择哪种模式？**
#
# A: 根据需求选择：
#
# **新手 / 单用户使用 → 便携模式**
#+ - ✅ 不需要配置，开箱即用
#+ - ✅ 想随时移动项目位置
#+ - ✅ 需要把项目发给别人
#+
# **高级用户 / 多项目团队 → 共享模式**
#+ - ✅ 同时在用多个 AI 项目
#+ - ✅ 磁盘空间紧张
#+ - ✅ 有专门的模型管理团队
#+
# ---
#
# **Q2: 如何确认当前使用的是哪种模式？**
#
# A: 查看项目启动日志，会显示：
#
# ```
# [INFO] 模型来源模式：portable
# [INFO] 模型目录：C:\...\Project\pretrained_models
# ```
#
# 或在浏览器打开 `http://localhost:<端口>/api/config` 查看配置。
#
# ---
#
# **Q3: 切换模式后需要重启吗？**
#
# A: 是的，修改 `.env` 文件或 `config.yaml` 后，需要重新启动应用程序。
#
# ---
#
# **Q4: 多个项目共用模型时需要注意什么？**
#
# A: 确保模型目录结构一致：
#
# ```bash
# # 推荐的标准结构
# AI_Shared_Models/
# ├── VoxCPM2/                  # 用于 Image & TTS
# ├── IndexTTS2/                # 用于 TTS
# ├── Z_image_turbo/            # 用于 Image
# └── SenseVoiceSmall/          # 用于 TTS (ASR)
# ```
#
# **检查点**:
# 1. 模型文件是否完整（包括 config.json、model.safetensors 等）
# 2. 目录名称是否与项目配置中的 `model_dir` 字段一致
# 3. 是否有正确的读权限
#
# ---
#
# **Q5: 路径包含中文会出问题吗？**
#
# A: **强烈建议避免中文路径**！某些 Python 库对中文路径支持不佳。
#
# ❌ 错误示例：
#+ ```env
# COMFY_MODELS_ROOT=D:\我的 AI 模型
# ```
#
# ✅ 正确示例：
#+ ```env
# COMFY_MODELS_ROOT=D:/AI_Models
# ```
#
# ---
#
# **Q6: Windows 路径用什么分隔符？**
#
# A: 推荐使用正斜杠 `/`，Python 完全兼容：
#
# ✅ 推荐：
#+ ```env
# COMFY_MODELS_ROOT=D:/AI_Models
# ```
#
# ✅ 也可用：
#+ ```env
# COMFY_MODELS_ROOT=D:\\AI_Models
# ```
#
# ❌ 避免：
#+ ```env
# COMFY_MODELS_ROOT=D:\AI_Models  # 可能出错（反斜杠被解释为转义字符）
# ```
#
# ---
#
# **Q7: macOS/Linux 如何使用波浪号 ~**？
#
# A: 直接在 `.env` 中使用 `~` 即可，Python 的 `Path.expanduser()` 会自动处理：
#
# ```env
# COMFY_MODELS_ROOT=~/AI_Models
# ```
#
# ---
#

## 🔒 安全注意事项
#
# 1. **.env 文件已被 .gitignore 忽略，绝不会提交到 Git**
# 2. **不要在 .env 中放置真实的 API 私钥（特别是私钥）**
# 3. **生产环境建议使用 secrets 管理系统而非 .env 文件**
# 4. **定期清理不再使用的模型文件释放磁盘空间**
#
---
#

## 📈 性能优化建议
#
# **SSD vs HDD**:
#+ - **强烈推荐将模型放在 SSD**，加载速度提升 10-20 倍
#
# **符号链接技巧**（节省磁盘空间）:
#+ ```powershell
# Windows 示例：让多个项目指向同一物理位置
# mklink /J "D:\ProjectA\pretrained_models" "D:\SharedModels"
#
# Mac/Linux 示例：
# ln -s /mnt/data/AI_Models ~/Projects/ProjectA/pretrained_models
# ```
#
# **缓存策略**:
#+ - Seedvr2 和 Image_MultiModel 支持输出缓存
#+ - 在 `.env` 中设置 `CACHE_DIR=/path/to/fast/storage`
#
---
#

## 🛠️ 故障排查
#
# **问题：程序提示"路径不存在"**
#
# **诊断步骤**:
# 1. 检查 `.env` 文件是否存在（如果使用共享模式）
#+ ```powershell
# dir .env  # Windows
# ls -la .env  # Mac/Linux
# ```
#
# 2. 验证环境变量是否生效:
#+ ```powershell
# echo %COMFY_MODELS_ROOT%  # Windows
# echo $COMFY_MODELS_ROOT   # Mac/Linux
# ```
#
# 3. 手动确认目录存在:
#+ ```powershell
# dir "D:\AI_Shared_Models"  # 替换为您的实际路径
# ```
#
# 4. 如果不存在，创建它:
#+ ```powershell
# mkdir "D:\AI_Shared_Models"
# ```
#
# ---
#

## 📝 相关文档索引
#
# ### Image_MultiModel
#+ - [README.md](Image_MultiModel/README.md)
#+ - [.env.example](Image_MultiModel/.env.example)
#+ - [docs/PATH-CONFIGURATION.md](Image_MultiModel/docs/PATH-CONFIGURATION.md)
#+ - [config.yaml](Image_MultiModel/config.yaml)
#
# ### TTS_MultiModel
#+ - [README.md](TTS_MultiModel/README.md)
#+ - [.env.example](TTS_MultiModel/.env.example)
#+ - [docs/PATH-CONFIGURATION.md](TTS_MultiModel/docs/PATH-CONFIGURATION.md) *TODO*
#+ - [config.yaml](TTS_MultiModel/config.yaml)
#
# ### Seedvr2
#+ - [README.md](Seedvr2/README.md)
#+ - [.env.example](Seedvr2/.env.example)
#+ - [docs/PATH-CONFIGURATION.md](Seedvr2/docs/PATH-CONFIGURATION.md) *TODO*
#+ - [config.yaml](Seedvr2/config.yaml)
#
# ### SpiritPal
#+ - [README.md](SpiritPal/README.md)
#+ - [.env.example](SpiritPal/.env.example)
#+ - [src/fix_route_persistence.ps1](SpiritPal/src/fix_route_persistence.ps1)
#+ - [tauri.conf.json](SpiritPal/src-tauri/tauri.conf.json)
#
# ### DraftPeek
#+ - [README.md](DraftPeek/README.md)
#+ - [Android 开发者文档](https://developer.android.com/guide/topics/data/data-storage)
#
---
#
# ================================================================================
# 文档版本：1.0.0  
# 最后更新：2026-08-15  
# 维护者：多项目路径配置优化小组  
# ================================================================================
