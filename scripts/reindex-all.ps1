param(
    [string]$DbHost = "127.0.0.1",
    [int]$DbPort = 3306,
    [string]$DbName = "rag_qa",
    [string]$DbUser = "root",
    [string]$DbPassword = "1234",
    [string]$PythonUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Write-Step($Message) {
    Write-Host "[reindex-all] $Message"
}

$mysql = Get-Command mysql -ErrorAction SilentlyContinue
if (-not $mysql) {
    throw "mysql command not found. Install MySQL client or run reindex through backend upload."
}

$query = "SELECT JSON_OBJECT('fileId', id, 'fileName', file_name, 'filePath', file_path) FROM knowledge_file WHERE status = 'SUCCESS' ORDER BY id"
$ConnectionArguments = @(
    "--host=$DbHost",
    "--port=$DbPort",
    "--user=$DbUser",
    "--password=$DbPassword",
    "--database=$DbName",
    "--default-character-set=utf8mb4",
    "--batch",
    "--raw",
    "--skip-column-names"
)

$PreviousEncoding = [Console]::OutputEncoding
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
try {
    $rows = & mysql @ConnectionArguments "--execute=$query"
    if ($LASTEXITCODE -ne 0) { throw "Cannot read file metadata from MySQL" }
} finally {
    [Console]::OutputEncoding = $PreviousEncoding
}
if (-not $rows) {
    Write-Step "No SUCCESS files found"
    exit 0
}

$success = 0
$failed = 0
foreach ($row in $rows) {
    $record = $row | ConvertFrom-Json
    $fileId = [int]$record.fileId
    $fileName = [string]$record.fileName
    $filePath = [string]$record.filePath

    if (-not (Test-Path -LiteralPath $filePath)) {
        Write-Step "Missing file for fileId=$fileId path=$filePath"
        $failed++
        continue
    }

    $body = @{
        fileId = $fileId
        fileName = $fileName
        filePath = $filePath
    } | ConvertTo-Json -Compress

    try {
        $response = Invoke-RestMethod -Uri "$PythonUrl/rag/index" `
            -Method Post `
            -ContentType "application/json; charset=utf-8" `
            -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) `
            -TimeoutSec 120
        if ($response.code -eq 200) {
            $chunkCount = [int]$response.data.chunkCount
            if ($chunkCount -lt 1) { throw "Indexer returned no chunks" }
            $update = "UPDATE knowledge_file SET chunk_count=$chunkCount, updated_at=NOW(), error_msg=NULL WHERE id=$fileId AND status='SUCCESS'"
            & mysql @ConnectionArguments "--execute=$update"
            if ($LASTEXITCODE -ne 0) { throw "Index is ready but the MySQL chunk count update failed" }
            Write-Step "Indexed fileId=$fileId fileName=$fileName chunks=$($response.data.chunkCount)"
            $success++
        } else {
            Write-Step "Failed fileId=$fileId msg=$($response.msg)"
            $failed++
        }
    } catch {
        Write-Step "Failed fileId=$fileId error=$($_.Exception.Message)"
        $failed++
    }
}

Write-Step "Done. success=$success failed=$failed"
if ($failed -gt 0) {
    exit 1
}
