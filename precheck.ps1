# precheck.ps1 - push 前本地预检
param([switch]$Full)
$ErrorActionPreference = 'Continue'
$script:failed = $false

# python 解析回退：.venv -> PATH python（家族分发器同款口径，兼容无 venv 环境）
$py = ".\\.venv\\Scripts\\python.exe"
if (-not (Test-Path $py)) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $py) {
  Write-Host "[precheck] 未找到 python（.venv 或 PATH），预检降级为仅告警，完整门禁由 GitHub CI 承担" -ForegroundColor Yellow
  exit 0
}

function Step($name, [scriptblock]$cmd) {
  Write-Host "==> $name"
  & $cmd
  if ($LASTEXITCODE -ne 0) { Write-Host "[FAIL] $name" -ForegroundColor Red; $script:failed = $true }
  else { Write-Host "[PASS] $name" -ForegroundColor Green }
}
function WarnSkip($name, $why) {
  Write-Host "==> $name [SKIP]（$why，完整门禁由 GitHub CI 承担）" -ForegroundColor Yellow
}
function HavePyModule($m) {
  & $py -c "import $m" 2>$null
  return ($LASTEXITCODE -eq 0)
}

if (HavePyModule "ruff") { Step "ruff lint" { & $py -m ruff check app/ tests/ } }
else { WarnSkip "ruff lint" "未安装 ruff" }
if (HavePyModule "mypy") { Step "mypy type check" { & $py -m mypy app/integrated_app } }
else { WarnSkip "mypy type check" "未安装 mypy" }
if ($Full) {
  if ((HavePyModule "pytest") -and (HavePyModule "app.integrated_app")) {
    Step "pytest + coverage" { & $py -m pytest --cov=app/integrated_app --cov-report=xml -q }
    # 阈值与 CI 门禁一致（ci.yml Coverage Gate >= 65% / pyproject fail_under=65）；此前写死 60% 导致本地全绿但 CI 报红
    Step "coverage gate >= 65%" { & $py -c "import xml.etree.ElementTree as ET; r=float(ET.parse('coverage.xml').getroot().get('line-rate')); p=r*100; print(f'{p:.1f}%'); assert p>=65, 'FAIL'" }
  }
  else { WarnSkip "pytest + coverage" "未安装 pytest 或应用依赖缺失（无 venv）" }
}
if ($script:failed) { Write-Host "`n预检未通过 - 修复后再 push" -ForegroundColor Red; exit 1 }
Write-Host "`n预检全绿 - 可以 push" -ForegroundColor Green
exit 0
