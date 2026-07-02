import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001',
  timeout: 120000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    return Promise.reject(new Error(typeof msg === 'string' ? msg : JSON.stringify(msg)))
  },
)

export default api

export const authApi = {
  login: (email, password) => api.post('/api/v1/auth/login', { email, password }),
  register: (data) => api.post('/api/v1/auth/register', data),
  me: () => api.get('/api/v1/auth/me'),
}

export const llmApi = {
  get: () => api.get('/api/v1/settings/llm'),
  update: (data) => api.put('/api/v1/settings/llm', data),
  test: () => api.post('/api/v1/settings/llm/test'),
}

export const contentApi = {
  list: (params) => api.get('/api/v1/content', { params }),
  get: (id) => api.get(`/api/v1/content/${id}`),
  generate: (data) => api.post('/api/v1/content/generate', data),
  submitReview: (id, comment = '') =>
    api.post(`/api/v1/content/${id}/submit-review`, { comment }),
  approve: (id, comment = '') => api.post(`/api/v1/content/${id}/approve`, { comment }),
  reject: (id, comment = '') => api.post(`/api/v1/content/${id}/reject`, { comment }),
}
