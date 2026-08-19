/**
 * 商家端内容文件 URL（封面/课时媒体等）需鉴权；img/video 无法带 Authorization，追加 access_token。
 */
export function authShopFileUrl(url) {
  const s = String(url || '').trim()
  if (!s) return ''
  if (!s.includes('/shop/content/files/')) return s
  let token = ''
  try {
    token = localStorage.getItem('token') || ''
  } catch {
    return s
  }
  if (!token) return s
  try {
    const base = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
    const u = new URL(s, base)
    u.searchParams.set('access_token', token)
    if (s.startsWith('http://') || s.startsWith('https://')) return u.toString()
    return `${u.pathname}${u.search}`
  } catch {
    const sep = s.includes('?') ? '&' : '?'
    return `${s}${sep}access_token=${encodeURIComponent(token)}`
  }
}
