import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
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
    const text = typeof msg === 'string' ? msg : JSON.stringify(msg)
    const status = err.response?.status
    if (
      status === 401 &&
      (text.includes('用户不存在') || text.includes('登录已失效') || text.includes('未登录'))
    ) {
      localStorage.removeItem('token')
      if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(new Error(text))
  },
)

export default api

export const authApi = {
  login: (phone, password) => api.post('/api/v1/auth/login', { phone, password }),
  sendSmsCode: (phone) => api.post('/api/v1/auth/sms/send', { phone }),
  loginBySms: (phone, code) => api.post('/api/v1/auth/sms/login', { phone, code }),
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
  calendar: () => api.get('/api/v1/content/calendar'),
  proposals: (data) => api.post('/api/v1/content/proposals', data),
  generate: (data) => api.post('/api/v1/content/generate', data),
  submitReview: (id, comment = '') =>
    api.post(`/api/v1/content/${id}/submit-review`, { comment }),
  approve: (id, comment = '') => api.post(`/api/v1/content/${id}/approve`, { comment }),
  reject: (id, comment = '') => api.post(`/api/v1/content/${id}/reject`, { comment }),
  schedule: (id, scheduledAt) =>
    api.post(`/api/v1/content/${id}/schedule`, { scheduled_at: scheduledAt }),
  publish: (id) => api.post(`/api/v1/content/${id}/publish`),
  retryPublish: (id) => api.post(`/api/v1/content/${id}/retry-publish`),
  exportXhs: (id) => api.post(`/api/v1/content/${id}/export/xhs`),
  exportDouyin: (id) => api.post(`/api/v1/content/${id}/export/douyin`),
  exportScript: (id) => api.post(`/api/v1/content/${id}/export/script`),
}

export const dashboardApi = {
  stats: () => api.get('/api/v1/dashboard/stats'),
}

export const analyticsApi = {
  stats: () => api.get('/api/v1/analytics/stats'),
}

export const knowledgeApi = {
  list: () => api.get('/api/v1/knowledge/documents'),
  uploadText: (data) => api.post('/api/v1/knowledge/documents/text', data),
  uploadFile: (formData) =>
    api.post('/api/v1/knowledge/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  remove: (id) => api.delete(`/api/v1/knowledge/documents/${id}`),
}

export const templatesApi = {
  list: (params) => api.get('/api/v1/templates', { params }),
}

export const assistantsApi = {
  list: () => api.get('/api/v1/assistants'),
}

export const brandApi = {
  get: () => api.get('/api/v1/settings/brand'),
  update: (data) => api.put('/api/v1/settings/brand', data),
  getUserPrompt: () => api.get('/api/v1/settings/user-prompt'),
  updateUserPrompt: (data) => api.put('/api/v1/settings/user-prompt', data),
}

export const wechatApi = {
  get: () => api.get('/api/v1/settings/wechat'),
  bindMock: (accountName, accountType = 'service') =>
    api.post('/api/v1/settings/wechat/bind-mock', {
      account_name: accountName,
      account_type: accountType,
    }),
}

export const adminApi = {
  listContents: (params) => api.get('/api/v1/admin/contents', { params }),
  listUsers: (params) => api.get('/api/v1/admin/users', { params }),
  updateUser: (id, data) => api.patch(`/api/v1/admin/users/${id}`, data),
  resetUserPassword: (id, password) =>
    api.post(`/api/v1/admin/users/${id}/reset-password`, { password }),
  deleteUser: (id) => api.delete(`/api/v1/admin/users/${id}`),
  listKnowledge: () => api.get('/api/v1/admin/knowledge/documents'),
  uploadKnowledgeText: (data) => api.post('/api/v1/admin/knowledge/documents/text', data),
  removeKnowledge: (id) => api.delete(`/api/v1/admin/knowledge/documents/${id}`),
  listAssistants: (params) => api.get('/api/v1/admin/assistants', { params }),
  createAssistant: (data) => api.post('/api/v1/admin/assistants', data),
  updateAssistant: (code, data) => api.patch(`/api/v1/admin/assistants/${code}`, data),
}
