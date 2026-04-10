param(
    [string]$PythonCommand = "python",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $projectRoot ".venv-build"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $projectRoot "dist\win32-x64"
}

# 先准备独立构建环境，避免污染系统 Python。
if (-not (Test-Path $venvPython)) {
    & $PythonCommand "-m" "venv" $venvRoot
}

& $venvPython "-m" "pip" "install" "--upgrade" "pip"

& $venvPython "-m" "pip" "install" "-r" (Join-Path $projectRoot "tools\requirements-build.txt")

& $venvPython `
    (Join-Path $projectRoot "tools\build_palworld_parser.py") `
    "--output-dir" `
    $OutputDir `
    "--binary-name" `
    "palworld-save-analysis" `
    "--clean"

Write-Host "构建完成: $OutputDir"
