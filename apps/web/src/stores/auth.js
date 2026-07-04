import { defineStore } from 'pinia'
import { authApi } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: null,
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
  },
  actions: {
    setToken(token) {
      this.token = token
      localStorage.setItem('token', token)
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
    },
    async fetchMe() {
      if (!this.token) return null
      try {
        const { data } = await authApi.me()
        this.user = data
        return data
      } catch (e) {
        this.logout()
        throw e
      }
    },
    async login(phone, password) {
      const { data } = await authApi.login(phone, password)
      this.setToken(data.access_token)
      await this.fetchMe()
    },
    async loginBySms(phone, code) {
      const { data } = await authApi.loginBySms(phone, code)
      this.setToken(data.access_token)
      await this.fetchMe()
    },
    async register(payload) {
      const { data } = await authApi.register(payload)
      this.setToken(data.access_token)
      await this.fetchMe()
    },
  },
})
