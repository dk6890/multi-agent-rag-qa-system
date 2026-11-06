param([switch]$SkipModelDownload)

$ErrorActionPreference = "Stop"
$RagDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) "rag-python"
$PythonExecutable = Join-Path $RagDirectory ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    python -m venv --system-site-packages (Join-Path $RagDirectory ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create the project Python environment" }
}
& $PythonExecutable -m pip install --disable-pip-version-check -r (Join-Path $RagDirectory "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "RAG dependency installation failed" }
if (-not $SkipModelDownload) {
    Push-Location $RagDirectory
    try {
        & $PythonExecutable -m embedding.prepare_model
        if ($LASTEXITCODE -ne 0) { throw "Local embedding model preparation failed" }
    } finally {
        Pop-Location
    }
}
