# pack_portable.ps1 — 便携包打包发布（PRD §10.5 七步 Checklist 自动化）
# 用法:
#   powershell -ExecutionPolicy Bypass -File scripts\pack_portable.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\pack_portable.ps1 -SkipZip
param(
    [switch]$SkipZip          # 只准备目录，不打 7z
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ConfigFile = Join-Path $ProjectRoot "config.yaml"
$OutZip = Join-Path (Split-Path -Parent $ProjectRoot) "Image_MultiModel_v1.0.0_portable.7z"

Write-Host "=== Image MultiModel · 便携包打包（PRD §10.5）===" -ForegroundColor Cyan

# STEP 1: 确认应用未运行（简易：检查端口占用提示）
Write-Host "[STEP 1] 请确认应用已关闭（释放文件句柄）..." -ForegroundColor Yellow
Write-Host "        检查: Get-NetTCPConnection -LocalPort 8288 | Select LocalPort,State"

# STEP 2: 切换 config.yaml → portable
Write-Host "[STEP 2] 切换 model_source_mode → portable" -ForegroundColor Cyan
$content = Get-Content $ConfigFile -Raw
$content = $content -replace "model_source_mode:\s*""?shared""?", "model_source_mode: `"portable`""
Set-Content $ConfigFile $content -Encoding UTF8
Write-Host "        config.yaml 已切换为 portable" -ForegroundColor Green

# STEP 3: 复制模型进 pretrained_models/
Write-Host "[STEP 3] 从 shared.comfy_models_dir 复制模型进 pretrained_models/（text_encoders/unet/vae）" -ForegroundColor Cyan
$ComfyDir = ""
if ($content -match "comfy_models_dir:\s*""?(?<dir>[^""\r\n]+)""?") { $ComfyDir = $Matches["dir"].TrimEnd("\") }
if (-not $ComfyDir) {
    Write-Warning "        无法从 config.yaml 读取 comfy_models_dir，跳过模型复制"
} else {
    # 本应用所需模型家族（原根目录 Junction 指向的 aki 目录）
    $CopyPlan = @{
        "text_encoders" = @("text_encoders", @("Z_image(turbo)"))
        "unet"          = @("unet", @("Z-image_turbo-bf16"))
        "vae"           = @("vae", @("FLUX.1-dev(Z-image(turbo))"))
    }
    foreach ($dest in $CopyPlan.Keys) {
        $subDir = $CopyPlan[$dest][0]
        $families = $CopyPlan[$dest][1]
        $dst = Join-Path $ProjectRoot "pretrained_models\$dest"
        if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Path $dst -Force | Out-Null }
        foreach ($fam in $families) {
            $src = Join-Path (Join-Path $ComfyDir $subDir) $fam
            if (Test-Path $src) {
                Copy-Item (Join-Path $src "*") (Join-Path $dst $fam) -Recurse -Force
                Write-Host "        已复制 $subDir/$fam" -ForegroundColor Green
            } else {
                Write-Warning "        源目录不存在，跳过: $src"
            }
        }
    }
}
Write-Host "        ⚠ 请确认 pretrained_models/seedvr2 含 ema_vae_fp16 + seedvr2_ema_3b_fp16（便携包必带）" -ForegroundColor Yellow

# STEP 4: 内嵌 Python 与 vendored 推理内核（comfy_kernel/）
Write-Host "[STEP 4] 人工步骤：内嵌 WinPython / comfy_kernel 推理内核（参考 PRD §10.5 STEP 4）" -ForegroundColor Yellow
Write-Host "        许可提示：comfy_kernel/ 为 ComfyUI 内核（GPL-3.0，上游 https://github.com/Comfy-Org/ComfyUI）。" -ForegroundColor Yellow
Write-Host "        随便携包分发时必须：① 保留 comfy_kernel/LICENSE 与 COMPLIANCE-README.md；" -ForegroundColor Yellow
Write-Host "        ② 在发布说明披露发行物中 ComfyUI 部分受 GPL-3.0 约束；③ 提供对应源代码获取方式。" -ForegroundColor Yellow

# STEP 5: 清理开发期残留
Write-Host "[STEP 5] 清理开发残留（cache/uploads/logs/Junction/字节码）" -ForegroundColor Cyan
foreach ($p in @("data\cache", "data\uploads", "logs")) {
    $full = Join-Path $ProjectRoot $p
    if (Test-Path $full) { Remove-Item (Join-Path $full "*") -Recurse -Force -ErrorAction SilentlyContinue }
}
foreach ($j in @("text", "unet", "vae")) {
    $link = Join-Path $ProjectRoot $j
    if (Test-Path $link) {
        $item = Get-Item $link -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Remove-Item $link -Force
            Write-Host "        已移除 Junction: $j" -ForegroundColor Green
        }
    }
}
Get-ChildItem $ProjectRoot -Recurse -Include *.pyc -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "        清理完成" -ForegroundColor Green

# STEP 6: 7z 打包 + SHA256
if ($SkipZip) {
    Write-Host "[STEP 6] 跳过打包（-SkipZip）" -ForegroundColor Yellow
} else {
    Write-Host "[STEP 6] 7z 打包（固实压缩，可分卷）" -ForegroundColor Cyan
    Write-Host "        注意：打包目录含 comfy_kernel/（ComfyUI，GPL-3.0）。分发前须完成 STEP 4 许可提示要求：" -ForegroundColor Yellow
    Write-Host "        随附 comfy_kernel/LICENSE 与 COMPLIANCE-README.md，并披露发行物受 GPL-3.0 约束。" -ForegroundColor Yellow
    $sevenZip = Get-Command 7z -ErrorAction SilentlyContinue
    if ($sevenZip) {
        Push-Location (Split-Path -Parent $ProjectRoot)
        & 7z a -t7z -m0=lzma2 -mx=7 $OutZip (Split-Path -Leaf $ProjectRoot)
        Pop-Location
        if (Test-Path $OutZip) {
            $hash = (Get-FileHash $OutZip -Algorithm SHA256).Hash
            Set-Content (Join-Path (Split-Path -Parent $ProjectRoot) "Image_MultiModel_v1.0.0_portable.7z.sha256") $hash
            Write-Host "        已生成: $OutZip" -ForegroundColor Green
            Write-Host "        SHA256: $hash" -ForegroundColor Green
        }
    } else {
        Write-Warning "        未找到 7z 命令，请手工打包并生成 SHA256"
    }
}

# STEP 7: 冒烟清单提示
Write-Host "[STEP 7] 在干净新机器上按 PRD §10.5 STEP 7 冒烟验收（7 项）" -ForegroundColor Cyan
Write-Host "        1) 解压到非中文路径  2) start.bat 15s 内开浏览器  3) 唯一 Z-Image Turbo 引擎"
Write-Host "        4) 加载 Z-Image Turbo ≤30s  5) 生成 1 张出 3 图  6) 关闭无残留  7) QA Pass"
Write-Host "=== 打包流程结束 ===" -ForegroundColor Green
