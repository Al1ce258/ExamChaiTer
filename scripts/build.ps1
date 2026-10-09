$ErrorActionPreference = "Stop"

if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }

uv run python scripts/gen_icon.py
uv run pyinstaller --clean --noconfirm ExamChaiTer.spec

if (-not (Test-Path dist/ExamChaiTer.exe)) {
    throw "Build failed: dist/ExamChaiTer.exe not found"
}

uv run python scripts/verify_exe.py
if ($LASTEXITCODE -ne 0) {
    throw "Build smoke failed: dist/ExamChaiTer.exe"
}

Write-Host "OK: dist/ExamChaiTer.exe"
