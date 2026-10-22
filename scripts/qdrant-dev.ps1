<#
.SYNOPSIS
    Start, stop and check the local Qdrant used for retrieval.

.DESCRIPTION
    Docker Compose is the documented way to run Qdrant for development:

        docker compose up -d qdrant

    When Docker is installed but its daemon is not running, this script falls
    back to the standalone Qdrant binary, which needs no container runtime. The
    binary is downloaded once into .data\qdrant and is not part of the
    repository.

    Examples:
        .\scripts\qdrant-dev.ps1 start
        .\scripts\qdrant-dev.ps1 status
        .\scripts\qdrant-dev.ps1 stop
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'status', 'restart')]
    [string]$Action = 'status',

    [int]$Port = 6333
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $root '.data\qdrant'
$composeFile = Join-Path $root 'docker-compose.yml'
$url = "http://127.0.0.1:$Port"

function Test-Qdrant {
    try {
        $response = Invoke-RestMethod -Uri "$url/readyz" -TimeoutSec 3
        return $true
    } catch {
        return $false
    }
}

function Test-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
    try {
        $version = docker info --format '{{.ServerVersion}}' 2>$null
        return [bool]$version
    } catch {
        return $false
    }
}

function Get-StandaloneBinary {
    $name = if ($IsWindows) { 'qdrant.exe' } else { 'qdrant' }
    return Join-Path $dataDir $name
}

function Install-Standalone {
    $binary = Get-StandaloneBinary
    if (Test-Path $binary) { return $binary }
    Write-Host 'Downloading the standalone Qdrant binary (one time, about 40 MB)...'
    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
    $url = 'https://github.com/qdrant/qdrant/releases/download/v1.19.1/qdrant-x86_64-pc-windows-msvc.zip'
    $zip = Join-Path $dataDir 'qdrant.zip'
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $dataDir -Force
    Remove-Item $zip -Force
    return $binary
}

switch ($Action) {
    'start' {
        if (Test-Qdrant) {
            Write-Host "Qdrant is already running at $url"
            exit 0
        }
        if (Test-Docker) {
            Write-Host 'Starting Qdrant with Docker Compose...'
            docker compose -f $composeFile up -d qdrant
        } else {
            Write-Host 'Docker is not running. Starting the standalone Qdrant binary...'
            $binary = Install-Standalone
            $env:QDRANT__SERVICE__HTTP_PORT = "$Port"
            $env:QDRANT__SERVICE__GRPC_PORT = "$($Port + 1)"
            $env:QDRANT__STORAGE__STORAGE_PATH = (Join-Path $dataDir 'storage')
            $env:QDRANT__STORAGE__SNAPSHOTS_PATH = (Join-Path $dataDir 'snapshots')
            Start-Process -FilePath $binary -WorkingDirectory $dataDir -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $dataDir 'qdrant.out.log') `
                -RedirectStandardError (Join-Path $dataDir 'qdrant.err.log')
        }
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            if (Test-Qdrant) {
                Write-Host "Qdrant is ready at $url"
                exit 0
            }
        }
        Write-Error "Qdrant did not become ready at $url"
        exit 1
    }
    'stop' {
        if (Test-Docker) {
            docker compose -f $composeFile down
        }
        $process = Get-Process -Name 'qdrant' -ErrorAction SilentlyContinue
        if ($process) {
            $process | Stop-Process -Force
            Write-Host 'Stopped the standalone Qdrant process.'
        }
        exit 0
    }
    'status' {
        if (Test-Qdrant) {
            Write-Host "Qdrant is running at $url"
            try {
                $collections = Invoke-RestMethod -Uri "$url/collections" -TimeoutSec 5
                $names = ($collections.result.collections | ForEach-Object { $_.name }) -join ', '
                Write-Host "Collections: $names"
            } catch {
                Write-Host 'Collections could not be listed.'
            }
        } else {
            Write-Host "Qdrant is not answering at $url"
            exit 1
        }
        exit 0
    }
    'restart' {
        & $PSScriptRoot 'qdrant-dev.ps1' stop
        & $PSScriptRoot 'qdrant-dev.ps1' start
        exit $LASTEXITCODE
    }
}
