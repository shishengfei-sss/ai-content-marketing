# 检查本地 API 是否包含最新 CRM/Team 接口
param(
    [int]$Port = 8003
)

$ErrorActionPreference = "Stop"
$url = "http://127.0.0.1:$Port/openapi.json"
try {
    $spec = Invoke-RestMethod -Uri $url -TimeoutSec 5
} catch {
    Write-Host "[FAIL] API 未响应: $url"
    exit 1
}

$leadParams = @($spec.paths.'/api/v1/crm/leads'.get.parameters | ForEach-Object { $_.name })
$hasFilters = $leadParams -contains 'filters'
$teamPath = $spec.paths.'/api/v1/team/members/{membership_id}'
$hasEditName = $null -ne $teamPath -and $teamPath.patch

Write-Host "API: http://127.0.0.1:$Port"
Write-Host "  高级筛选 filters: $(if ($hasFilters) { 'OK' } else { '缺失' })"
Write-Host "  编辑姓名 PATCH:   $(if ($hasEditName) { 'OK' } else { '缺失' })"

if (-not $hasFilters -or -not $hasEditName) {
    Write-Host "[FAIL] 当前 API 版本过旧，请运行 scripts/restart-api.cmd"
    exit 1
}

Write-Host "[OK] API 功能完整"
exit 0
