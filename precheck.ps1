# precheck.ps1 - push 前本地预检
param([switch]$Full)
$ErrorActionPreference = 'Continue'
$script:failed = $false
$py = ".\.venv\Scripts\python.exe"
function Step($name, [scriptblock]$cmd) {
  Write-Host "==> $name"
  & $cmd
  if ($LASTEXITCODE -ne 0) { Write-Host "[FAIL] $name" -ForegroundColor Red; $script:failed = $true }
  else { Write-Host "[PASS] $name" -ForegroundColor Green }
}
Step "ruff lint" { & $py -m ruff check app/ tests/ }
Step "mypy type check" { & $py -m mypy app/integrated_app }
if ($Full) {
  Step "pytest + coverage" { & $py -m pytest --cov=app/integrated_app --cov-report=xml -q }
  Step "coverage gate >= 60%" { & $py -c "import xml.etree.ElementTree as ET; r=float(ET.parse('coverage.xml').getroot().get('line-rate')); p=r*100; print(f'{p:.1f}%'); assert p>=60, 'FAIL'" }
}
if ($script:failed) { Write-Host "`n预检未通过 - 修复后再 push" -ForegroundColor Red; exit 1 }
Write-Host "`n预检全绿 - 可以 push" -ForegroundColor Green
exit 0