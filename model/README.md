# Image_MultiModel 模型目录说明（符号链接 / Junction）

> 本目录（`Image_MultiModel\model`）下**不再存放真实模型文件**。
> 所有模型均已迁移至 ComfyUI 的 `models` 目录，本目录仅保留指向它们的**目录符号链接（Windows Junction）**。
> 模型物理文件**只存在一份**（位于 ComfyUI），Image_MultiModel 与 ComfyUI 两侧共用，**不会产生磁盘冗余**。

---

## 一、为什么这样做

- **避免冗余**：模型文件体积大（本目录涉及的 17 个文件合计约 132.7 GB）。此前曾以"复制"方式在两侧各存一份，会浪费等量磁盘空间。
- **两侧共用**：ComfyUI 直接读取真实文件；Image_MultiModel 通过 Junction 以**与原路径完全一致**的方式访问，引擎无需任何改动。
- **Junction 特性**：Windows 目录交接点，对应用透明（读取/加载如同普通目录），创建**不需要管理员权限**，也无需开启开发者模式。

## 二、链接结构（链接 → 实际位置）

| 类别 | 本目录下的链接 | 指向（真实文件所在） |
| --- | --- | --- |
| unet | `unet\FLUX.1-dev-fp8` | `APP\ComfyUI-aki-v3\ComfyUI\models\unet\FLUX.1-dev-fp8` |
| unet | `unet\FLUX.2-klein-9b-fp8` | `APP\ComfyUI-aki-v3\ComfyUI\models\unet\FLUX.2-klein-9b-fp8` |
| unet | `unet\Z-image-bf16` | `APP\ComfyUI-aki-v3\ComfyUI\models\unet\Z-image-bf16` |
| unet | `unet\Z-image_turbo-bf16` | `APP\ComfyUI-aki-v3\ComfyUI\models\unet\Z-image_turbo-bf16` |
| text_encoders | `text_encoders\FLUX.1-dev` | `APP\ComfyUI-aki-v3\ComfyUI\models\text_encoders\FLUX.1-dev` |
| text_encoders | `text_encoders\FLUX.2-klein-9b` | `APP\ComfyUI-aki-v3\ComfyUI\models\text_encoders\FLUX.2-klein-9b` |
| text_encoders | `text_encoders\Z_image(turbo)` | `APP\ComfyUI-aki-v3\ComfyUI\models\text_encoders\Z_image(turbo)` |
| vae | `vae\FLUX.1-dev(Z-image(turbo))` | `APP\ComfyUI-aki-v3\ComfyUI\models\vae\FLUX.1-dev(Z-image(turbo))` |
| vae | `vae\FLUX.2-klein-9b` | `APP\ComfyUI-aki-v3\ComfyUI\models\vae\FLUX.2-klein-9b` |

> ComfyUI 根目录为 `C:\Users\Doro\APP\ComfyUI-aki-v3\ComfyUI`。

## 三、使用方法（两侧一致）

- **Image_MultiModel**：无需任何配置改动，按原路径（如 `model\unet\FLUX.1-dev-fp8\...`）即可加载模型，Junction 透明转发到 ComfyUI 真实文件。
- **ComfyUI-aki-v3**：直接在 `models\unet`、`models\text_encoders`、`models\vae` 下正常使用真实文件。

## 四、维护注意事项

1. **不要在本目录下的链接里直接改动文件内容**——写入会穿透到 ComfyUI 的真实文件。
2. **删除模型**：请先删除 ComfyUI 中的真实文件，再删除本目录对应链接；顺序反了会导致链接指向空目标。
3. **新增模型**：先把真实文件放入 ComfyUI `models` 对应类别目录，再在本目录对应类别下创建 Junction：
   ```powershell
   New-Item -ItemType Junction -Path "<本目录>\<类别>\<模型名>" -Target "<ComfyUI>\models\<类别>\<模型名>"
   ```
4. **校验链接是否有效**：
   ```powershell
   Get-ChildItem "<本目录>" -Recurse -Directory | Where-Object LinkType -eq 'Junction' | Select-Object FullName, Target
   ```
5. **删除/重建链接不影响真实文件**，删除 Junction 本身不会删除目标数据。

## 五、本次迁移记录（2026-08-19）

- 从本目录移至 ComfyUI 的模型：FLUX.1-dev-fp8 ×4、FLUX.2-klein-9b-fp8 ×5、Z-image-bf16 ×1、Z-image_turbo-bf16 ×2、t5xxl te、qwen3-8b te、qwen3-4b te、ae vae、flux2-vae，共 17 个文件（约 132.7 GB）。
- 迁移方式：逐目录移动至 ComfyUI → 校验文件存在与大小一致 → 原路径建立 Junction（本目录）。
