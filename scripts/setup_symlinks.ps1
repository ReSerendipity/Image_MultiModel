# setup_symlinks.ps1 — 【已退役】shared 模式 Junction 符号链接维护（PRD §10.4）
#
# ⚠️ 2026-08-13 起停用：运行时已不再依赖根目录 Junction。
#    · shared 模式：resolve_engine_model_paths 直接读 config.yaml → shared.comfy_models_dir（aki 路径）
#    · portable 模式：模型统一放 pretrained_models/
#    · 根目录 text/ unet/ vae/ 链接已删除，避免误导模型摆放。
#    本脚本保留仅作历史参考，不再执行。
# 用法（已停用，仅提示）:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_symlinks.ps1

param(
    [switch]$Uninstall
)

Write-Host "=== setup_symlinks.ps1 已退役（2026-08-13）===" -ForegroundColor Yellow
Write-Host "运行时不再使用根目录 Junction。shared 模式直接走 shared.comfy_models_dir。"
Write-Host "如需在本机重建旧式链接请参考 git 历史，本脚本不再维护。"
exit 0
