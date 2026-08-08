Image MultiModel — 便携模式 (portable) 内置模型目录
====================================================

本目录结构 1:1 镜像 ComfyUI\models\ 的子目录，用途：
  MODE = "portable"（config.yaml → models.model_source_mode = "portable"）
  时，代码会从该目录读取模型，不再依赖外部 ComfyUI 的符号链接。

如何切换为便携包（发给用户 / 拷到 U 盘 / 新机器）:
  1. 关闭应用
  2. 打开 config.yaml，修改 models.model_source_mode: "shared" → "portable"
  3. 把 C:\Users\Doro\APP\ComfyUI-aki-v3\ComfyUI\models 下
     对应的子目录内容复制到：
       text_encoders/   → 文本编码器 (qwen_3_Xb_fp8mixed.safetensors)
       unet/            → DiT / UNet 权重 (BigLoveKlein2 / z_image_turbo 等)
       vae/             → VAE 解码器 (ae.safetensors / flux2-vae.safetensors)
       loras/           → LoRA 权重 (可选)
       controlnet/      → ControlNet 权重 (可选)
       checkpoints/     → 整模型 Checkpoints (可选)
  4. 重新启动 start.bat。应用会读取 pretrained_models/ 下的真实
     模型文件，整个目录即可独立拷贝到任何新机器运行。

切回 shared 开发模式：
  1. 还原 models.model_source_mode = "shared"
  2. 确保项目根下 text/ unet/ vae/ 的 Junction 符号链接指回
     外部 ComfyUI\models（脚本可一键重建，见 scripts/setup_symlinks.ps1 预留）
