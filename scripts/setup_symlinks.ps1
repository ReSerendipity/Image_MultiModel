# setup_symlinks.ps1 — shared 模式 Junction 符号链接维护（PRD §10.4）
# 用法:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_symlinks.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\setup_symlinks.ps1 -Uninstall
param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ConfigFile = Join-Path $ProjectRoot "config.yaml"

Write-Host "=== Image MultiModel · Junction 维护脚本 ===" -ForegroundColor Cyan

# 1. 检测模式
if (-not (Test-Path $ConfigFile)) {
    Write-Error "config.yaml 不存在: $ConfigFile"
    exit 1
}
$yaml = Get-Content $ConfigFile -Raw
if ($yaml -notmatch "model_source_mode:\s*""?shared""?") {
    Write-Warning "config.yaml 不是 shared 模式（应为 models.model_source_mode: shared）。退出。"
    exit 1
}
Write-Host "[1/5] 模式: shared (Junction 共享外部 ComfyUI 模型)" -ForegroundColor Green

# 2. 解析 comfy_models_dir 与 mount_map
if ($yaml -notmatch "comfy_models_dir:\s*""?(?<dir>[^""\r\n]+)""?") {
    Write-Error "config.yaml 缺少 shared.comfy_models_dir"
    exit 1
}
$ComfyModels = $Matches["dir"].TrimEnd("\")
if (-not (Test-Path $ComfyModels)) {
    Write-Error "ComfyUI models 目录不可读: $ComfyModels"
    exit 1
}
Write-Host "[2/5] ComfyUI models: $ComfyModels" -ForegroundColor Green

# mount_map: 项目子目录 → ComfyUI 子目录
$MountMap = @{
    "text"        = "text_encoders"
    "unet"        = "unet"
    "vae"         = "vae"
    "loras"       = "loras"
    "controlnet"  = "controlnet"
    "checkpoints" = "checkpoints"
}

# 3. 建立 / 移除 Junction
foreach ($key in $MountMap.Keys) {
    $link = Join-Path $ProjectRoot $key
    $target = Join-Path $ComfyModels $MountMap[$key]

    if ($Uninstall) {
        if (Test-Path $link) {
            $item = Get-Item $link -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                Remove-Item $link -Force
                Write-Host "  已移除 Junction: $link" -ForegroundColor Yellow
            } else {
                Write-Warning "  跳过（普通目录，非 Junction）: $link"
            }
        }
        continue
    }

    if (-not (Test-Path $target)) {
        Write-Warning "  目标不存在，跳过: $target"
        continue
    }
    if (Test-Path $link) {
        $item = Get-Item $link -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Write-Host "  已存在 Junction，跳过: $link" -ForegroundColor DarkGray
        } else {
            $backup = "$link`_待删除"
            Write-Host "  普通目录存在 → 重命名为 $backup" -ForegroundColor Yellow
            Rename-Item $link $backup
            New-Item -ItemType Junction -Path $link -Target $target | Out-Null
            Write-Host "  已创建 Junction: $link → $target" -ForegroundColor Green
        }
    } else {
        New-Item -ItemType Junction -Path $link -Target $target | Out-Null
        Write-Host "  已创建 Junction: $link → $target" -ForegroundColor Green
    }
}

# 4. 校验
Write-Host "[4/5] 校验链接:" -ForegroundColor Cyan
foreach ($key in $MountMap.Keys) {
    $link = Join-Path $ProjectRoot $key
    if (-not $Uninstall -and (Test-Path $link)) {
        $n = (Get-ChildItem $link -File -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
        Write-Host "  $key : $n 个文件"
    }
}

Write-Host "[5/5] 完成。" -ForegroundColor Green
