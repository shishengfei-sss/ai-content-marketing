import { authApi } from './api'
import { clearToken, getToken, setToken } from './auth'

const USER_KEY = 'ai_marketing_user'

export function getCachedUser() {
  try {
    return JSON.parse(uni.getStorageSync(USER_KEY) || 'null')
  } catch {
    return null
  }
}

export function setCachedUser(user) {
  if (user) uni.setStorageSync(USER_KEY, JSON.stringify(user))
  else uni.removeStorageSync(USER_KEY)
}

export async function fetchMe() {
  const data = await authApi.me()
  setCachedUser(data)
  return data
}

export async function afterAuth(data) {
  setToken(data.access_token)
  const me = await fetchMe()
  if (me.need_select_tenant) {
    uni.reLaunch({ url: '/pages/select-tenant/select-tenant' })
    return me
  }
  uni.switchTab({ url: '/pages/index/index' })
  return me
}

export async function ensureSession() {
  if (!getToken()) {
    uni.reLaunch({ url: '/pages/login/login' })
    return null
  }
  let user = getCachedUser()
  if (!user) user = await fetchMe()
  if (user?.need_select_tenant) {
    uni.reLaunch({ url: '/pages/select-tenant/select-tenant' })
    return null
  }
  return user
}

export async function selectTenant(tenantId) {
  const data = await authApi.selectTenant(tenantId)
  setToken(data.access_token)
  await fetchMe()
}

export async function switchTenant(tenantId) {
  const data = await authApi.switchTenant(tenantId)
  setToken(data.access_token)
  await fetchMe()
}

export function logout() {
  clearToken()
  setCachedUser(null)
  uni.reLaunch({ url: '/pages/login/login' })
}
