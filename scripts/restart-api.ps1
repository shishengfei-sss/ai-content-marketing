# 重启本地 API（默认 8000）。若端口被旧进程占用，会先尝试结束占用进程。
param(
    [int]$Port = 8000
)

$ErrorActionPreference = "SilentlyContinue"
$apiRoot = Join-Path $PSScriptRoot ".." "apps" "api" | Resolve-Path

Write-Host "Stopping listeners on port $Port ..."
$pids = @()
try {
    $pids = Get-NetTCPConnection -LocalPort $Port -State Listen |
        Select-Object -ExpandProperty OwningProcess -Unique
} catch {
    $lines = netstat -ano | Select-String ":$Port\s+.*LISTENING"
    foreach ($line in $lines) {
        $procId = ($line -replace '\s+', ' ').Trim().Split(' ')[-1]
        if ($procId -match '^\d+$') { $pids += [int]$procId }
    }
}
$pids = $pids | Select-Object -Unique
foreach ($procId in $pids) {
    Write-Host "  taskkill PID $procId"
    taskkill /F /PID $procId | Out-Null
}
Start-Sleep -Seconds 1

Write-Host "Starting API on http://127.0.0.1:$Port ..."
Set-Location $apiRoot
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
