# 重启本地 API（默认 8003）。会清理本项目 uvicorn 及 8002/8003 端口占用。
param(
    [int]$Port = 8003
)

$ErrorActionPreference = "SilentlyContinue"
$apiRoot = Join-Path $PSScriptRoot ".." "apps" "api" | Resolve-Path
$apiRootEscaped = [regex]::Escape($apiRoot.Path)

function Stop-ProjectApiProcesses {
    Write-Host "Stopping all uvicorn / spawn workers for this project ..."
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $cmd = $_.CommandLine
            if (-not $cmd) { return $false }
            # 主进程 / reload 子进程 / multiprocessing.spawn worker
            return (
                ($cmd -match "uvicorn app\.main:app" -and $cmd -match $apiRootEscaped) -or
                ($cmd -match "multiprocessing\.spawn" -and $cmd -match "spawn_main")
            )
        } |
        ForEach-Object {
            Write-Host "  taskkill python PID $($_.ProcessId)"
            taskkill /F /T /PID $_.ProcessId 2>$null | Out-Null
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

Stop-ProjectApiProcesses

foreach ($cleanupPort in (@(8002, 8003, $Port) | Select-Object -Unique)) {
    Write-Host "Stopping listeners on port $cleanupPort ..."
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        $pids = @()
        try {
            $pids += Get-NetTCPConnection -LocalPort $cleanupPort -State Listen -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty OwningProcess -Unique
        } catch {}
        $lines = netstat -ano | Select-String ":$cleanupPort\s+.*LISTENING"
        foreach ($line in $lines) {
            $procId = ($line -replace '\s+', ' ').Trim().Split(' ')[-1]
            if ($procId -match '^\d+$') { $pids += [int]$procId }
        }
        $pids = $pids | Where-Object { $_ -gt 0 } | Select-Object -Unique
        if (-not $pids) { break }
        foreach ($procId in $pids) {
            Write-Host "  taskkill port-owner PID $procId (attempt $attempt)"
            taskkill /F /T /PID $procId 2>$null | Out-Null
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
        # spawn worker 可能挂在已杀父进程下，再扫一轮
        Stop-ProjectApiProcesses
        Start-Sleep -Seconds 1
    }
}

Start-Sleep -Seconds 1
try {
    $still = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 2
    if ($still) {
        Write-Host "WARN: port $Port still answering health — check lingering python manually"
    }
} catch {
    Write-Host "Port $Port is free."
}

Write-Host ""
Write-Host "Starting API on http://127.0.0.1:$Port ..."
Write-Host "Web/H5 proxy: VITE_API_PROXY_TARGET=http://127.0.0.1:$Port"
Write-Host "After .env change, restart Web/H5 (npm run dev)"
Write-Host "Windows: WATCHFILES_FORCE_POLLING=1 (avoid fake reload)"
Write-Host ""

Set-Location $apiRoot
# Windows 下默认 inotify 等价机制常漏检/半重载；强制轮询更稳
$env:WATCHFILES_FORCE_POLLING = '1'
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload --reload-dir app
