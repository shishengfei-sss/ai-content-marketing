import { defineStore } from 'pinia'
import { authApi } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: null,
    needSelectTenant: false,
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
    permissions: (state) => state.user?.permissions || [],
    hasPermission: (state) => (code) => (state.user?.permissions || []).includes(code),
    activeTenantName: (state) => state.user?.active_tenant?.name || '',
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
    async login(phone, password) {
      const { data } = await authApi.login(phone, password)
      this.setToken(data.access_token, data.need_select_tenant)
      await this.fetchMe()
    },
    async loginBySms(phone, code) {
      const { data } = await authApi.loginBySms(phone, code)
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
  },
})
