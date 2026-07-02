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
      const { data } = await authApi.me()
      this.user = data
      return data
    },
    async login(email, password) {
      const { data } = await authApi.login(email, password)
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
