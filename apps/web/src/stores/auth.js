import { defineStore } from 'pinia'
import { authApi } from '../api/client'

export const WORKSPACE_PLATFORM = 'platform'
export const WORKSPACE_MERCHANT = 'merchant'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: null,
    needSelectTenant: false,
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
    permissions: (state) => state.user?.permissions || [],
    platformShopPermissions: (state) => state.user?.platform_shop_permissions || [],
    hasPermission: (state) => (code) => (state.user?.permissions || []).includes(code),
    hasPlatformShopPermission: (state) => (code) =>
      (state.user?.platform_shop_permissions || []).includes(code),
    hasAnyPlatformShopPermission: (state) => (codes) => {
      const set = new Set(state.user?.platform_shop_permissions || [])
      return codes.some((c) => set.has(c))
    },
    activeTenantName: (state) => state.user?.active_tenant?.name || '',
    workspaceMode: (state) => state.user?.workspace_mode || WORKSPACE_MERCHANT,
    hasMerchantWorkspace: (state) => !!state.user?.has_merchant_workspace,
    isPlatformAdmin: (state) => state.user?.role === 'platform_admin',
    isPlatformWorkspace: (state) =>
      state.user?.role === 'platform_admin' && state.user?.workspace_mode === WORKSPACE_PLATFORM,
    isMerchantWorkspace: (state) => state.user?.workspace_mode === WORKSPACE_MERCHANT,
    canSwitchWorkspace: (state) =>
      state.user?.role === 'platform_admin' && state.user?.has_merchant_workspace,
    /** 对照 #a08-clerk：店员仅核销台 */
    isShopClerk: (state) => {
      if (state.user?.active_tenant?.role_code === 'shop_clerk') return true
      const tid = state.user?.active_tenant?.id
      const hit = (state.user?.tenants || []).find((t) => String(t.id) === String(tid))
      return (hit?.role_code || '') === 'shop_clerk'
    },
  },
  actions: {
    setToken(token, needSelect = false) {
      this.token = token
      this.needSelectTenant = needSelect
      localStorage.setItem('token', token)
    },
    logout() {
      this.token = ''
      this.user = null
      this.needSelectTenant = false
      localStorage.removeItem('token')
    },
    async fetchMe() {
      if (!this.token) return null
      try {
        const { data } = await authApi.me()
        this.user = data
        this.needSelectTenant = !!data.need_select_tenant
        return data
      } catch (e) {
        this.logout()
        throw e
      }
    },
    async login(phone, password, workspaceMode = WORKSPACE_MERCHANT) {
      const { data } = await authApi.login(phone, password, workspaceMode)
      this.setToken(data.access_token, data.need_select_tenant)
      await this.fetchMe()
    },
    async loginBySms(phone, code, workspaceMode = WORKSPACE_MERCHANT) {
      const { data } = await authApi.loginBySms(phone, code, workspaceMode)
      this.setToken(data.access_token, data.need_select_tenant)
      await this.fetchMe()
    },
    async register(payload) {
      const { data } = await authApi.register(payload)
      this.setToken(data.access_token, data.need_select_tenant)
      await this.fetchMe()
    },
    async selectTenant(tenantId) {
      const { data } = await authApi.selectTenant(tenantId)
      this.setToken(data.access_token, false)
      await this.fetchMe()
    },
    async switchTenant(tenantId) {
      const { data } = await authApi.switchTenant(tenantId)
      this.setToken(data.access_token, false)
      await this.fetchMe()
    },
    async switchWorkspace(workspaceMode) {
      const { data } = await authApi.switchWorkspace(workspaceMode)
      this.setToken(data.access_token, data.need_select_tenant)
      await this.fetchMe()
    },
  },
})
