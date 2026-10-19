param(
    [int]$Port = 27017
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$dataPath = Join-Path $repoRoot ".data\mongo"
$logPath = Join-Path $repoRoot ".data\mongod.log"

if (-not (Get-Command mongod -ErrorAction SilentlyContinue)) {
    throw "mongod was not found on PATH. Install MongoDB or start it manually and set MONGODB_URI."
}

New-Item -ItemType Directory -Force -Path $dataPath | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $logPath) | Out-Null

$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Host "MongoDB is already listening on port $Port."
    exit 0
}

Start-Process -FilePath "mongod" `
    -ArgumentList @("--dbpath", "`"$dataPath`"", "--port", $Port, "--bind_ip", "127.0.0.1") `
    -RedirectStandardOutput $logPath `
    -RedirectStandardError "$logPath.err" `
    -WindowStyle Hidden

Start-Sleep -Seconds 2
$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    throw "MongoDB did not start. Check $logPath and $logPath.err"
}

Write-Host "MongoDB listening on 127.0.0.1:$Port (data: $dataPath)"
