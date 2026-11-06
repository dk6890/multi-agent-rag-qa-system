param(
    [switch]$BuildFrontend,
    [switch]$Reindex,
    [int]$FrontendPort = 5173,
    [int]$BackendPort = 8080,
    [int]$PythonPort = 8000
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendDir = Join-Path $Root "backend-java"
$FrontendDir = Join-Path $Root "frontend-vue"

function Write-Step($Message) {
    Write-Host "[start-all] $Message"
}

function Test-Http($Url, [int]$TimeoutSec = 3) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSec
        if ($Url -match '/api/') {
            $payload = $response.Content | ConvertFrom-Json
            if ($payload.code -ne 200) { return $null }
        }
        return [int]$response.StatusCode
    } catch {
        return $null
    }
}

function Wait-Http($Name, $Url, [int]$Seconds = 45) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        $code = Test-Http -Url $Url
        if ($code -ge 200 -and $code -lt 300) {
            Write-Step "$Name ready: $Url ($code)"
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "$Name did not become ready within $Seconds seconds: $Url"
}

function Start-CmdFile($Name, $Path) {
    $fullPath = (Resolve-Path -LiteralPath $Path).Path
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "cmd.exe"
    $psi.Arguments = '/c "' + $fullPath + '"'
    $psi.WorkingDirectory = Split-Path -Parent $fullPath
    $psi.UseShellExecute = $true
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $process = [System.Diagnostics.Process]::Start($psi)
    if ($null -eq $process) {
        throw "Could not start $Name"
    }
    $process.Dispose()
}

Write-Step "Stopping old services"
& (Join-Path $PSScriptRoot "stop-all.ps1") -Ports @($FrontendPort, $BackendPort, $PythonPort)

if ($BuildFrontend -or -not (Test-Path (Join-Path $FrontendDir "dist\index.html"))) {
    Write-Step "Building frontend"
    Push-Location $FrontendDir
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
    } finally {
        Pop-Location
    }
}

New-Item -ItemType Directory -Path (Join-Path $BackendDir "target") -Force | Out-Null

Write-Step "Starting Python RAG on port $PythonPort"
Start-CmdFile "rag-python" (Join-Path $PSScriptRoot "run-python-rag.cmd")
Wait-Http "Python RAG" "http://127.0.0.1:$PythonPort/health" 45
Write-Step "Checking the real local embedding model"
$EmbeddingHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$PythonPort/health?loadEmbedding=true" -TimeoutSec 45
if ($EmbeddingHealth.embedding.status -ne "ready") {
    throw "Semantic embedding is unavailable. Run scripts\prepare-rag.ps1, then restart."
}

Write-Step "Starting Java backend on port $BackendPort"
Start-CmdFile "rag-backend" (Join-Path $PSScriptRoot "run-backend.cmd")
Wait-Http "Java backend" "http://127.0.0.1:$BackendPort/api/files/list" 60

if ($Reindex) {
    Write-Step "Reindexing SUCCESS files"
    & (Join-Path $PSScriptRoot "reindex-all.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Some files could not be reindexed; inspect the reindex output" }
}

Write-Step "Starting frontend preview on port $FrontendPort"
Start-CmdFile "rag-frontend" (Join-Path $PSScriptRoot "run-frontend.cmd")
Wait-Http "Frontend" "http://127.0.0.1:$FrontendPort/" 30
Wait-Http "Frontend API proxy" "http://127.0.0.1:$FrontendPort/api/files/list" 30

Write-Step "All services are ready"
Write-Host ""
Write-Host "Frontend : http://127.0.0.1:$FrontendPort/"
Write-Host "Backend  : http://127.0.0.1:$BackendPort"
Write-Host "Python   : http://127.0.0.1:$PythonPort"
