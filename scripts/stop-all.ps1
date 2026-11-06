param(
    [int[]]$Ports = @(5173, 8080, 8000)
)

$ErrorActionPreference = "Stop"

function Write-Step($Message) {
    Write-Host "[stop-all] $Message"
}

function Get-PidsByPort([int]$Port) {
    $lines = netstat -ano | Select-String -Pattern "[:.]$Port\s"
    foreach ($line in $lines) {
        $parts = ($line.ToString() -split "\s+") | Where-Object { $_ }
        if ($parts.Length -ge 5 -and $parts[1] -match "[:.]$Port$") {
            [int]$parts[-1]
        }
    }
}

$pids = @()
foreach ($port in $Ports) {
    $pids += Get-PidsByPort -Port $port
}

$pids = $pids | Where-Object { $_ -gt 0 } | Sort-Object -Unique
if (-not $pids) {
    Write-Step "No services found on ports: $($Ports -join ', ')"
    exit 0
}

foreach ($processId in $pids) {
    try {
        $process = Get-Process -Id $processId -ErrorAction Stop
        Write-Step "Stopping PID $processId ($($process.ProcessName))"
        Stop-Process -Id $processId -Force -ErrorAction Stop
    } catch {
        Write-Step "PID $processId already stopped or cannot be queried"
    }
}

Start-Sleep -Seconds 2
Write-Step "Done"
