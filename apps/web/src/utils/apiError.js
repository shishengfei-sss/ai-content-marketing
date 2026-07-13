/** FastAPI 路由不存在（常见于旧 API 未重启）时的 404。 */
export function isRouteNotFoundError(err) {
  if (err?.status !== 404) return false
  const msg = String(err?.message || '').trim().toLowerCase()
  return msg === 'not found' || msg.includes('status code 404') || msg.includes('request failed with status code 404')
}

/** 列表/搜索无结果：路由 404 时按空列表处理，不弹红条。 */
export function isBenignEmptyError(err) {
  return isRouteNotFoundError(err)
}

export function applyEmptyListFallback(err, apply) {
  if (isBenignEmptyError(err)) {
    apply()
    return true
  }
  return false
}

/** 加载设置页：路由 404 时保留默认表单，不提示。 */
export function shouldSilenceLoadError(err) {
  return isRouteNotFoundError(err)
}

export const ROUTE_NOT_FOUND_HINT =
  '后端接口不可用，请重启 API 并确认 Web 代理端口（VITE_API_PROXY_TARGET）一致'

export const INTERNAL_SERVER_HINT =
  '服务器内部错误：请确认已执行 alembic upgrade head、配置 DEEPSEEK_API_KEY，并查看 docker logs ai_marketing_api'

export function formatApiError(err, fallback = '操作失败') {
  if (isRouteNotFoundError(err)) return ROUTE_NOT_FOUND_HINT
  const msg = String(err?.message || fallback).trim()
  if (msg.toLowerCase() === 'not found') return ROUTE_NOT_FOUND_HINT
  if (msg.toLowerCase() === 'internal server error' || msg.includes('status code 500')) {
    return INTERNAL_SERVER_HINT
  }
  return msg || fallback
}

export function workflowErrorMessage(workflow) {
  if (!workflow) return ''
  if (workflow.error_message) return String(workflow.error_message)
  const failed = (workflow.steps || []).find((s) => s.status === 'failed')
  if (failed?.error_message) return String(failed.error_message)
  return ''
}
