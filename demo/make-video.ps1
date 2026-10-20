<#
.SYNOPSIS
    Record the BidKaro demo walkthrough, add local narration and encode an MP4.

.DESCRIPTION
    The recording tools (playwright, ffmpeg-static) are not repository
    dependencies. Install them in a scratch folder and pass that folder to
    this script:

        mkdir demo-tools
        cd demo-tools
        npm init -y
        npm i playwright ffmpeg-static
        npx playwright install chromium

    Then, from the repository root:

        .\demo\make-video.ps1 -ToolsPath <path-to-demo-tools>

    The backend must run on http://127.0.0.1:8000 and the frontend on
    http://localhost:5173. If local text-to-speech is unavailable the script
    reports it and still produces the captioned silent WebM.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ToolsPath,

    [string]$AppUrl = "http://localhost:5173",
    [string]$Email = "asha.phase1@example.com",
    [string]$Password = "BidKaro123",
    [string]$OutFile = "bidkaro-demo.mp4"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$recording = Join-Path $PSScriptRoot '.recording'
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$ffmpeg = Join-Path $ToolsPath 'node_modules\ffmpeg-static\ffmpeg.exe'

if (-not (Test-Path $ffmpeg)) {
    Write-Error "ffmpeg-static was not found at $ffmpeg. Run 'npm i ffmpeg-static' in $ToolsPath."
}
if (-not (Test-Path $python)) {
    Write-Error "The backend virtualenv was not found at $python."
}

if (Test-Path $recording) {
    Remove-Item -Recurse -Force $recording
}

$env:NODE_PATH = Join-Path $ToolsPath 'node_modules'
$env:DEMO_OUT_DIR = $recording
$env:DEMO_APP_URL = $AppUrl
$env:DEMO_EMAIL = $Email
$env:DEMO_PASSWORD = $Password

Write-Host 'Recording the walkthrough...'
& node (Join-Path $PSScriptRoot 'record-demo.cjs')
if ($LASTEXITCODE -ne 0) {
    Write-Error "Recording failed with exit code $LASTEXITCODE."
}

Write-Host 'Building narration and caption files...'
& $python (Join-Path $PSScriptRoot 'build-narration.py') --recording $recording
$narrationExit = $LASTEXITCODE
if ($narrationExit -eq 3) {
    Write-Warning 'Narration is unavailable on this machine. The captioned silent video will be produced instead.'
}

$video = Get-ChildItem (Join-Path $recording 'video\*.webm') | Select-Object -First 1
if (-not $video) {
    Write-Error 'No recorded video was found.'
}

$target = Join-Path $PSScriptRoot $OutFile
if ($narrationExit -eq 0) {
    Write-Host 'Encoding the captioned MP4 with narration...'
    & $ffmpeg -y -i $video.FullName -i (Join-Path $recording 'narration.wav') `
        -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 25 `
        -c:a aac -b:a 128k -ar 44100 -ac 1 -movflags +faststart -shortest $target
} else {
    Write-Host 'Encoding the captioned MP4 without narration...'
    & $ffmpeg -y -i $video.FullName `
        -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 25 `
        -movflags +faststart $target
}

Copy-Item (Join-Path $recording 'captions.srt') (Join-Path $PSScriptRoot 'captions.srt') -Force
Copy-Item (Join-Path $recording 'captions.vtt') (Join-Path $PSScriptRoot 'captions.vtt') -Force

Write-Host "Wrote $target"
