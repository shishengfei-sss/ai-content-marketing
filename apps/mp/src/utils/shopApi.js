/**
 * 买家商城 API（与智营员工 token 隔离，使用 shop_buyer_token）
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const TOKEN_KEY = 'shop_buyer_token'
const TENANT_KEY = 'shop_buyer_tenant_id'
const LOGOUT_KEY = 'shop_buyer_logged_out'
const SHOP_KEY = 'shop_buyer_shop_id'

export function getShopBuyerToken() {
  return uni.getStorageSync(TOKEN_KEY) || ''
}

export function setShopBuyerToken(token) {
  if (token) uni.setStorageSync(TOKEN_KEY, token)
  else uni.removeStorageSync(TOKEN_KEY)
}

export function getShopBuyerTenantId() {
  return uni.getStorageSync(TENANT_KEY) || ''
}

export function setShopBuyerTenantId(tenantId) {
  if (tenantId) uni.setStorageSync(TENANT_KEY, tenantId)
  else uni.removeStorageSync(TENANT_KEY)
}

export function clearShopBuyerSession() {
  setShopBuyerToken('')
  uni.setStorageSync(LOGOUT_KEY, '1')
}

export function getShopBuyerShopId() {
  return uni.getStorageSync(SHOP_KEY) || ''
}

export function setShopBuyerShopId(shopId) {
  if (shopId) uni.setStorageSync(SHOP_KEY, shopId)
  else uni.removeStorageSync(SHOP_KEY)
}

export function shopNavQuery({ shopId, tenantId, openid } = {}) {
  const sp = new URLSearchParams()
  const sid = shopId || getShopBuyerShopId()
  const tid = tenantId || getShopBuyerTenantId()
  if (sid) sp.set('shop_id', String(sid))
  if (tid) sp.set('tenant_id', String(tid))
  if (openid) sp.set('openid', String(openid))
  const qs = sp.toString()
  return qs ? `?${qs}` : ''
}

function shopRequest({ url, method = 'GET', data, auth = true }) {
  return new Promise((resolve, reject) => {
    const header = { 'Content-Type': 'application/json' }
    if (auth) {
      const token = getShopBuyerToken()
      if (token) header.Authorization = `Bearer ${token}`
    }
    uni.request({
      url: BASE_URL + url,
      method,
      data,
      header,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          const detail = res.data?.detail || '请求失败'
          const error = new Error(
            typeof detail === 'string' ? detail : detail.message || JSON.stringify(detail)
          )
          error.status = res.statusCode
          error.detail = detail
          reject(error)
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络错误'))
      },
    })
  })
}

function withQuery(path, params = {}) {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    sp.append(k, String(v))
  }
  const qs = sp.toString()
  return qs ? `${path}?${qs}` : path
}

export const shopBuyerApi = {
  login: (tenantId, code) =>
    shopRequest({
      url: '/api/v1/mp/shop/auth/login',
      method: 'POST',
      data: { tenant_id: tenantId, code },
      auth: false,
    }),
  bindMobile: async (mobile) => {
    const data = await shopRequest({
      url: '/api/v1/mp/shop/auth/bind',
      method: 'POST',
      data: { mobile },
    })
    if (data?.access_token) setShopBuyerToken(data.access_token)
    return data?.buyer || data
  },
  me: () => shopRequest({ url: '/api/v1/mp/shop/auth/me' }),
  getClaim: (token) =>
    shopRequest({
      url: `/api/v1/mp/shop/claim/${encodeURIComponent(token)}`,
      auth: false,
    }),
  getPendingClaim: () => shopRequest({ url: '/api/v1/mp/shop/claim/pending' }),
  confirmClaim: (token) =>
    shopRequest({
      url: `/api/v1/mp/shop/claim/${encodeURIComponent(token)}`,
      method: 'POST',
    }),
  listEntitlements: (params = {}) =>
    shopRequest({
      url: withQuery('/api/v1/mp/shop/entitlements', { page: 1, page_size: 50, ...params }),
    }),
  getOutline: (entitlementId) =>
    shopRequest({ url: `/api/v1/mp/shop/entitlements/${entitlementId}/outline` }),
  getMaterials: (entitlementId) =>
    shopRequest({ url: `/api/v1/mp/shop/entitlements/${entitlementId}/materials` }),
  downloadMaterial: (entitlementId, fileId) =>
    shopRequest({
      url: `/api/v1/mp/shop/entitlements/${entitlementId}/materials/${encodeURIComponent(fileId)}/download`,
      method: 'POST',
    }),
  upsertLessonProgress: (entitlementId, lessonId, body) =>
    shopRequest({
      url: `/api/v1/mp/shop/entitlements/${entitlementId}/lessons/${lessonId}/progress`,
      method: 'PUT',
      data: body,
    }),
  listOrders: (params = {}) =>
    shopRequest({
      url: withQuery('/api/v1/mp/shop/orders', { page: 1, page_size: 50, ...params }),
    }),
  getOrder: (orderId) => shopRequest({ url: `/api/v1/mp/shop/orders/${orderId}` }),
  cancelOrder: (orderId) =>
    shopRequest({ url: `/api/v1/mp/shop/orders/${orderId}/cancel`, method: 'POST', data: {} }),
  payOrder: (orderId) =>
    shopRequest({ url: `/api/v1/mp/shop/orders/${orderId}/pay`, method: 'POST', data: {} }),
  refundOrder: (orderId, body) =>
    shopRequest({
      url: `/api/v1/mp/shop/orders/${orderId}/refund`,
      method: 'POST',
      data: body,
    }),
  listOrderRefunds: (orderId) =>
    shopRequest({ url: `/api/v1/mp/shop/orders/${orderId}/refunds` }),
  listServiceSlots: (offerId, params = {}) =>
    shopRequest({
      url: withQuery(`/api/v1/mp/shop/service-offers/${offerId}/slots`, params),
    }),
  createBooking: (body) =>
    shopRequest({ url: '/api/v1/mp/shop/bookings', method: 'POST', data: body }),
  listBookings: (params = {}) =>
    shopRequest({
      url: withQuery('/api/v1/mp/shop/bookings', { page: 1, page_size: 50, ...params }),
    }),
  cancelBooking: (bookingId, reason) =>
    shopRequest({
      url: `/api/v1/mp/shop/bookings/${bookingId}/cancel`,
      method: 'POST',
      data: { reason: reason || '买家取消' },
    }),
  createInvoice: (body) =>
    shopRequest({ url: '/api/v1/mp/shop/invoices', method: 'POST', data: body }),
  listInvoices: (params = {}) =>
    shopRequest({
      url: withQuery('/api/v1/mp/shop/invoices', { page: 1, page_size: 50, ...params }),
    }),
  getStore: (params = {}) =>
    shopRequest({
      url: withQuery('/api/v1/mp/shop/store', params),
      auth: false,
    }),
  resolveStore: (tenantId) =>
    shopRequest({
      url: withQuery('/api/v1/mp/shop/store/resolve', { tenant_id: tenantId }),
      auth: false,
    }),
  getProduct: (productId) =>
    shopRequest({ url: `/api/v1/mp/shop/products/${productId}` }),
  createOrder: (productId) =>
    shopRequest({
      url: '/api/v1/mp/shop/orders',
      method: 'POST',
      data: { product_id: productId },
    }),
}

/** 补齐店首页所需的 shop_id / tenant_id（URL → 本地缓存 → 按租户解析） */
export async function ensureShopNavContext({ shopId = '', tenantId = '' } = {}) {
  let sid = (shopId || getShopBuyerShopId() || '').trim()
  let tid = (tenantId || getShopBuyerTenantId() || '').trim()
  if (!sid && tid) {
    try {
      const hit = await shopBuyerApi.resolveStore(tid)
      sid = hit?.shop_id ? String(hit.shop_id) : ''
    } catch {
      /* ignore */
    }
  }
  if (tid) setShopBuyerTenantId(tid)
  if (sid) setShopBuyerShopId(sid)
  return { shopId: sid, tenantId: tid }
}

/** 确保买家会话：按 tenant 用 mock openid 登录（开发/H5） */
export async function ensureShopBuyerSession(tenantId, openidHint) {
  if (!tenantId) throw new Error('缺少商家标识')
  const loggedOut = uni.getStorageSync(LOGOUT_KEY) === '1'
  if (loggedOut && !openidHint) {
    throw new Error('未登录')
  }
  const existing = getShopBuyerToken()
  const prevTenant = getShopBuyerTenantId()
  if (existing && prevTenant === String(tenantId) && !loggedOut) {
    try {
      return await shopBuyerApi.me()
    } catch {
      setShopBuyerToken('')
    }
  }
  const openid = openidHint || `mp_${Date.now().toString(36)}`
  const data = await shopBuyerApi.login(tenantId, `mock:${openid}`)
  setShopBuyerToken(data.access_token)
  setShopBuyerTenantId(String(tenantId))
  uni.removeStorageSync(LOGOUT_KEY)
  return data.buyer
}
