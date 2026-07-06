/** FastAPI 路由不存在（常见于旧 API 未重启）时的 404。 */
export function isRouteNotFoundError(err) {
  if (err?.status !== 404) return false
  const msg = String(err?.message || '').trim().toLowerCase()
  return msg === 'not found'
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

export function formatApiError(err, fallback = '操作失败') {
  if (isRouteNotFoundError(err)) return ROUTE_NOT_FOUND_HINT
  const msg = String(err?.message || fallback).trim()
  if (msg.toLowerCase() === 'not found') return ROUTE_NOT_FOUND_HINT
  return msg || fallback
}
