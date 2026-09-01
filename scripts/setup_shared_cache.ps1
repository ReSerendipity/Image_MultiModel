# setup_shared_cache.ps1 — 跨实例模型共享缓存初始化（P2·反模式 #3 修复）
#
# 替代已退役的 setup_symlinks.ps1：不再用 Junction 把模型摆进项目根，
# 而是准备一个「多实例共享的权重根目录」（如挂载卷 / 对象存储本地缓存），
# 供 config.yaml → models.shared_cache_dir 指向。portable 模式下权重解析会
# 优先命中该目录，缺失再回退 model/，实现「N 副本部署 = 1 份权重下载/存储」。
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_shared_cache.ps1 -CacheDir D:\shared_models
#
# 该脚本仅创建目录并打印配置提示，不移动/下载任何权重文件。

param(
    [string]$CacheDir = ""
)

if (-not $CacheDir) {
    Write-Host "用法: setup_shared_cache.ps1 -CacheDir <共享权重根目录>" -ForegroundColor Yellow
    Write-Host "示例: setup_shared_cache.ps1 -CacheDir D:\shared_models" -ForegroundColor Yellow
    exit 1
}

$cache = Resolve-Path -Path $CacheDir -ErrorAction SilentlyContinue
if (-not $cache) {
    New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null
    $cache = Resolve-Path -Path $CacheDir
}

# 预建子目录（与 model/ 下的 sub_dirs 对齐），方便运维摆放权重
$subDirs = @("text_encoders", "unet", "vae", "loras", "controlnet", "checkpoints")
foreach ($d in $subDirs) {
    New-Item -ItemType Directory -Path (Join-Path $cache $d) -Force | Out-Null
}

Write-Host "=== 跨实例共享缓存目录已就绪 ===" -ForegroundColor Green
Write-Host "路径: $cache"
Write-Host "请在 config.yaml 设置:" -ForegroundColor Cyan
Write-Host "  models:"
Write-Host "    shared_cache_dir: `"$cache`""
Write-Host "（权重按 text_encoders/ unet/ vae/ ... 子目录摆放，与 portable 模式路径一致）"
exit 0
