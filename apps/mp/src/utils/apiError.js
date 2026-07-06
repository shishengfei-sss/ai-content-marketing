/** FastAPI 路由不存在（常见于旧 API 未重启）时的 404。 */
export function isRouteNotFoundError(err) {
  if (err?.status !== 404) return false
  const msg = String(err?.message || '').trim().toLowerCase()
  return msg === 'not found'
}

/** 列表/搜索无结果：路由 404 时按空列表处理。 */
export function isBenignEmptyError(err) {
  return isRouteNotFoundError(err)
}

export function shouldSilenceLoadError(err) {
  return isRouteNotFoundError(err)
}

export function toastUnlessEmpty(err, fallback = '加载失败') {
  if (isBenignEmptyError(err)) return false
  uni.showToast({ title: err?.message || fallback, icon: 'none' })
  return true
}

export function toastApiError(err, fallback = '操作失败') {
  if (isRouteNotFoundError(err)) {
    uni.showToast({ title: ROUTE_NOT_FOUND_HINT, icon: 'none', duration: 3000 })
    return true
  }
  const msg = String(err?.message || fallback).trim()
  if (msg.toLowerCase() === 'not found') {
    uni.showToast({ title: ROUTE_NOT_FOUND_HINT, icon: 'none', duration: 3000 })
    return true
  }
  uni.showToast({ title: msg || fallback, icon: 'none' })
  return true
}

export const ROUTE_NOT_FOUND_HINT =
  '后端接口不可用，请运行 scripts/restart-api.cmd 8002 后刷新'

export function formatApiError(err, fallback = '操作失败') {
  if (isRouteNotFoundError(err)) return ROUTE_NOT_FOUND_HINT
  const msg = String(err?.message || fallback).trim()
  if (msg.toLowerCase() === 'not found') return ROUTE_NOT_FOUND_HINT
  return msg || fallback
}
