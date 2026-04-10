param(
    [string]$ServerRoot,
    [string]$BinaryPath = "",
    [string]$OutputFile = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($ServerRoot)) {
    throw "请提供服务端根目录，例如 C:\path\to\PalServer"
}

if ([string]::IsNullOrWhiteSpace($BinaryPath)) {
    $BinaryPath = Join-Path $projectRoot "dist\win32-x64\palworld-save-analysis.exe"
}

if (-not (Test-Path $BinaryPath)) {
    throw "未找到二进制文件: $BinaryPath"
}

$saveGamesRoot = Join-Path $ServerRoot "Pal\Saved\SaveGames"
if (-not (Test-Path $saveGamesRoot)) {
    throw "未找到存档目录: $saveGamesRoot"
}

$levelCandidates = Get-ChildItem -Path $saveGamesRoot -Recurse -File -Filter "Level.sav" |
    Sort-Object FullName

$levelFile = $levelCandidates |
    Where-Object { $_.FullName -notmatch "\\backup\\" } |
    Select-Object -First 1

if (-not $levelFile) {
    $levelFile = $levelCandidates | Select-Object -First 1
}

if (-not $levelFile) {
    throw "未找到 Level.sav"
}

$playersDir = Join-Path $levelFile.DirectoryName "Players"
if (-not (Test-Path $playersDir)) {
    throw "未找到 Players 目录: $playersDir"
}

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $outputDir = Join-Path $projectRoot "test-output"
    if (-not (Test-Path $outputDir)) {
        New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    }
    $OutputFile = Join-Path $outputDir "analysis.json"
}

# 做一次真实烟雾测试，确认二进制能完成解析并输出结构化 JSON。
$jsonText = & $BinaryPath --level $levelFile.FullName --players-dir $playersDir
$jsonText | Set-Content -Path $OutputFile -Encoding UTF8

$result = $jsonText | ConvertFrom-Json -Depth 100
if (-not $result.meta) {
    throw "解析结果缺少 meta 字段"
}
if ($null -eq $result.players) {
    throw "解析结果缺少 players 字段"
}
if ($null -eq $result.guilds) {
    throw "解析结果缺少 guilds 字段"
}

$playerCount = @($result.players).Count
$guildCount = @($result.guilds).Count
Write-Host "测试通过: 玩家 $playerCount 个, 公会 $guildCount 个"
Write-Host "Level.sav: $($levelFile.FullName)"
Write-Host "结果文件: $OutputFile"
