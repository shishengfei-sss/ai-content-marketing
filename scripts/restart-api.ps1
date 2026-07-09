# 重启本地 API（默认 8003）。会清理本项目 uvicorn 及 8002/8003 端口占用。
param(
    [int]$Port = 8003
)

$ErrorActionPreference = "SilentlyContinue"
$apiRoot = Join-Path $PSScriptRoot ".." "apps" "api" | Resolve-Path

Write-Host "Stopping all uvicorn (app.main:app) for this project ..."
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "uvicorn app\.main:app" -and $_.CommandLine -match [regex]::Escape($apiRoot.Path) } |
    ForEach-Object {
        Write-Host "  taskkill uvicorn PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

foreach ($cleanupPort in @(8002, 8003, $Port)) {
    Write-Host "Stopping listeners on port $cleanupPort ..."
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $pids = @()
        try {
            $pids = Get-NetTCPConnection -LocalPort $cleanupPort -State Listen -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty OwningProcess -Unique
        } catch {
            $lines = netstat -ano | Select-String ":$cleanupPort\s+.*LISTENING"
            foreach ($line in $lines) {
                $procId = ($line -replace '\s+', ' ').Trim().Split(' ')[-1]
                if ($procId -match '^\d+$') { $pids += [int]$procId }
            }
        }
        $pids = $pids | Where-Object { $_ -gt 0 } | Select-Object -Unique
        if (-not $pids) { break }
        foreach ($procId in $pids) {
            if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
                Write-Host "  taskkill PID $procId"
                taskkill /F /T /PID $procId 2>$null | Out-Null
            }
        }
        Start-Sleep -Seconds 1
    }
}

Start-Sleep -Seconds 1
Write-Host ""
Write-Host "Starting API on http://127.0.0.1:$Port ..."
Write-Host "Web/H5 代理请指向: VITE_API_PROXY_TARGET=http://127.0.0.1:$Port"
Write-Host "修改 .env 后需重启 Web/H5 开发服务 (npm run dev)"
Write-Host ""

Set-Location $apiRoot
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
