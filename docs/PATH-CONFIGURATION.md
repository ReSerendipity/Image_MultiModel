# Image_MultiModel 路径配置指南
# ================================================================================

# 🚀 快速开始（新手推荐）
# ----------------------------------------
#
# **您完全可以不做任何配置！**
#
# 本项目默认使用**便携模式（portable mode）**，所有路径都相对于项目根目录：
#
# ```bash
# git clone <仓库地址>
# cd Image_MultiModel
# pip install -r requirements.txt
# python bin/start.py  # 直接运行，无需修改任何配置！
# ```
#
# 在这种模式下：
# ✅ 模型下载到 `pretrained_models/` 目录
# ✅ 生成图片输出到 `outputs/` 目录
# ✅ 日志写入 `logs/` 目录
#
# **整个项目文件夹可以直接拷贝到任意位置，或者用压缩包发送给朋友，都能正常运行！**
#
# ---
#
# 🎯 两种部署模式对比
# ----------------------------------------
#
# | 特性 | **便携模式（portable）** | **共享模式（shared）** |
# |------|-------------------------|------------------------|
# | **适用场景** | 个人使用、新手入门 | 多项目共享、节省空间 |
# | **配置难度** | ⭐ 零配置 | ⭐⭐⭐ 需要配置环境变量 |
# | **磁盘占用** | 各项目独立保存模型 | 多个项目共享同一份模型 |
# | **可移植性** | ⭐⭐⭐⭐⭐ 极高 | ⭐⭐⭐ 中等 |
# | **推荐使用** | ✅ 推荐新手和单用户 | 适合高级用户和团队 |
#
# ---
#
# 方案 A：便携模式（推荐 90% 的用户）
# ----------------------------------------
#
# ### 什么是便携模式？
#
# 所有 AI 模型文件存储在项目的 `pretrained_models/` 目录下。
#
# **优点：**
# - ✅ 无需任何配置，clone 后直接运行
# - ✅ 可以离线使用
# - ✅ 发给别人也能直接使用
#
# **缺点：**
# - ⚠️ 多个项目会有重复模型，占用更多磁盘空间
# - ⚠️ 首次运行需要下载约 5-10GB 模型文件
#
# ### 如何使用？
#
# **什么都不用做！** 默认就是便携模式：
#
# ```yaml
# # config.yaml (第 13 行)
# models:
#   model_source_mode: portable  # ✅ 默认值
# ```
#
# ---
#
# 方案 B：共享模式（节省磁盘空间）
# ----------------------------------------
#
# ### 什么是共享模式？
#
# 将所有 AI 项目共用的模型存储在一个外部目录，多个项目指向同一个位置。
#
# **优点：**
# - ✅ 节省磁盘空间
# - ✅ 统一管理
#
# **缺点：**
# - ⚠️ 需要手动配置环境变量
# - ⚠️ 不方便分享给其他人
#
# ### Windows 配置步骤
#
# #### Step 1: 创建共享模型目录
#
# ```powershell
# mkdir D:\AIModels  # 建议在非系统盘
# ```
#
# #### Step 2: 复制环境变量模板
#
# ```powershell
# copy .env.example .env
# ```
#
# #### Step 3: 编辑 .env 文件
#
# 用记事本或 VS Code 打开 `.env` 文件：
#
# ```env
# IMAGE_MODEL_MODE=shared
# COMFY_MODELS_ROOT=D:\AIModels  # 替换为您的实际路径
# ```
#
# #### Step 4: 启动项目
#
# ```powershell
# python bin/start.py
# ```
#
# ### macOS / Linux 配置步骤
#
# ```bash
# # Step 1: 创建目录
# mkdir -p ~/AIModels
#
# # Step 2: 复制模板
# cp .env.example .env
#
# # Step 3: 编辑配置
# nano .env
# # 修改为：
# # IMAGE_MODEL_MODE=shared
# # COMFY_MODELS_ROOT=~/AIModels
#
# # Step 4: 启动
# python bin/start.py
# ```
#
# ---
#
# 🛠️ 环境变量说明
# ----------------------------------------
#
# | 变量名 | 说明 | 示例值 | 默认值 |
# |--------|------|---------|--------|
# | `IMAGE_MODEL_MODE` | 模型来源模式 | `portable` \| `shared` | `portable` |
# | `COMFY_MODELS_ROOT` | 共享模型目录 | `D:\AIModels` \| `/opt/models` | 无 |
# | `LOG_LEVEL` | 日志级别 | `DEBUG`\|`INFO`\|`WARNING` | `INFO` |
# | `LOG_PATH` | 日志文件路径 | `logs/app.log` | `logs/app.log` |
#
# ### 验证环境变量是否生效
#
# **Windows:**
# ```powershell
# set IMAGE_MODEL_MODE
# set COMFY_MODELS_ROOT
# ```
#
# **macOS/Linux:**
# ```bash
# echo $IMAGE_MODEL_MODE
# echo $COMFY_MODELS_ROOT
# ```
#
# ---
#
## 🔧 故障排查
# ----------------------------------------
#
# ### 问题 1: 程序提示"路径不存在"
#
# **解决方案:**
# 1. 检查 `.env` 中 `COMFY_MODELS_ROOT` 的值是否正确
# 2. 确认该目录确实存在:
#    ```powershell
#    dir D:\AIModels  # Windows
#    ls -la ~/AIModels  # Mac/Linux
#    ```
# 3. 如果不存在，创建它:
#    ```powershell
#    mkdir D:\AIModels  # Windows
#    mkdir -p ~/AIModels  # Mac/Linux
#    ```
#
# ### 问题 2: 路径包含中文导致失败
#
# ❌ 错误：`D:\我的模型目录`  
# ✅ 正确：`D:\AI_Models`
#
# ### 问题 3: 迁移模型到新位置
#
# **方案 1: 修改 .env 文件**
#
# ```env
# COMFY_MODELS_ROOT=E:\NewLocation\AIModels
# ```
#
# **方案 2: 创建符号链接**
#
# **Windows:**
# ```powershell
# mklink /J "D:\OldModels" "E:\NewLocation\AIModels"
# ```
#
# **macOS/Linux:**
# ```bash
# ln -s /E/NewLocation/AIModels ~/OldModels
# ```
#
# ---
#
## 💡 常见问题 FAQ
# ----------------------------------------
#
# **Q: 我应该选择哪种模式？**
#
# A: 
# - **新手/单人使用** → 便携模式（portable）
# - **多项目/企业部署** → 共享模式（shared）
#
# **Q: 切换模式后需要重启吗？**
#
# A: 是的，修改配置后需要重新启动应用程序。
#
# **Q: 如何确认当前使用的是哪种模式？**
#
# A: 程序启动时会打印日志:
# ```
# [INFO] 模型来源模式：portable
# [INFO] 模型目录：C:\...\Image_MultiModel\pretrained_models
# ```
#
# ---
#
## 📝 路径格式注意事项
# ----------------------------------------
#
# ### Windows 路径写法
#
# ✅ 推荐使用正斜杠:
# ```env
# COMFY_MODELS_ROOT=D:/AIModels
# ```
#
# ✅ 或使用双反斜杠:
# ```env
# COMFY_MODELS_ROOT=D:\\AIModels
# ```
#
# ❌ 避免单反斜杠:
# ```env
# COMFY_MODELS_ROOT=D:\AIModels  # ❌ 可能出错
# ```
#
# ---
#
## 📚 相关文档
# ----------------------------------------
#
- [README.md](../README.md) - 项目总览和快速开始
- [.env.example](../.env.example) - 环境变量模板
- [config.yaml](../config.yaml) - 主配置文件
#
# ================================================================================
# 文档版本：1.0.0  
# 最后更新：2026-08-15
# ================================================================================
