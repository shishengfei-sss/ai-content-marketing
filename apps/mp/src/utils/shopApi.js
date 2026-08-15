/**
 * 买家商城 API（与智营员工 token 隔离，使用 shop_buyer_token）
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const TOKEN_KEY = 'shop_buyer_token'
const TENANT_KEY = 'shop_buyer_tenant_id'

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
  bindMobile: (mobile) =>
    shopRequest({
      url: '/api/v1/mp/shop/auth/bind',
      method: 'POST',
      data: { mobile },
    }),
  me: () => shopRequest({ url: '/api/v1/mp/shop/auth/me' }),
  getClaim: (token) =>
    shopRequest({
      url: `/api/v1/mp/shop/claim/${encodeURIComponent(token)}`,
      auth: false,
    }),
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
  getProduct: (productId) =>
    shopRequest({ url: `/api/v1/mp/shop/products/${productId}` }),
  createOrder: (productId) =>
    shopRequest({
      url: '/api/v1/mp/shop/orders',
      method: 'POST',
      data: { product_id: productId },
    }),
}

/** 确保买家会话：按 tenant 用 mock openid 登录（开发/H5） */
export async function ensureShopBuyerSession(tenantId, openidHint) {
  if (!tenantId) throw new Error('缺少商家标识')
  const existing = getShopBuyerToken()
  const prevTenant = getShopBuyerTenantId()
  if (existing && prevTenant === String(tenantId)) {
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
  return data.buyer
}
