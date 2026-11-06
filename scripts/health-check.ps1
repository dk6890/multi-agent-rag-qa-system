param(
    [int]$FrontendPort = 5173,
    [int]$BackendPort = 8080,
    [int]$PythonPort = 8000
)

$ErrorActionPreference = "Continue"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Test-Endpoint($Name, $Url) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
        if ($Url -match '/api/' -and ($response.Content | ConvertFrom-Json).code -ne 200) {
            throw "Endpoint returned a non-success business code"
        }
        Write-Host "[OK]   $Name -> $Url ($($response.StatusCode))"
        return $true
    } catch {
        Write-Host "[FAIL] $Name -> $Url :: $($_.Exception.Message)"
        return $false
    }
}

function Get-RagHealth {
    try {
        return Invoke-RestMethod -Uri "http://127.0.0.1:$PythonPort/health?loadEmbedding=true" -TimeoutSec 30
    } catch {
        return $null
    }
}

$ok = $true
$ok = (Test-Endpoint "Frontend" "http://127.0.0.1:$FrontendPort/") -and $ok
$ok = (Test-Endpoint "Frontend API proxy" "http://127.0.0.1:$FrontendPort/api/files/list") -and $ok
$ok = (Test-Endpoint "Backend files API" "http://127.0.0.1:$BackendPort/api/files/list") -and $ok
$ok = (Test-Endpoint "Python health" "http://127.0.0.1:$PythonPort/health") -and $ok

$ragHealth = Get-RagHealth
if ($null -eq $ragHealth -or $ragHealth.embedding.status -ne "ready") {
    Write-Host "[FAIL] Real semantic embedding unavailable. Run scripts\prepare-rag.ps1 and restart Python."
    $ok = $false
} else {
    Write-Host "[OK]   Embedding ready: dimension=$($ragHealth.embedding.dimension), maxTokens=$($ragHealth.embedding.maxInputTokens)"
    $count = [int]$ragHealth.index.chunkCount
    if ($count -gt 0) {
        Write-Host "[OK]   Semantic chunks = $count, indexed files = $($ragHealth.index.indexedFiles)"
    } else {
        Write-Host "[WARN] Semantic index is empty. Run scripts\reindex-all.ps1."
    }
}

if ($ok) {
    Write-Host "[health-check] PASS"
    exit 0
}

Write-Host "[health-check] FAIL"
exit 1
