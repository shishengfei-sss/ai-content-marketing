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
  async (err) => {
    let text = err.message || '请求失败'
    const data = err.response?.data
    const status = err.response?.status
    if (data instanceof Blob) {
      try {
        const raw = await data.text()
        try {
          const parsed = JSON.parse(raw)
          if (typeof parsed.detail === 'string') {
            text = parsed.detail
          } else if (parsed.detail) {
            text = JSON.stringify(parsed.detail)
          } else {
            text = raw || text
          }
        } catch {
          text = raw || text
        }
      } catch {
        /* keep axios message */
      }
    } else if (data?.detail) {
      text = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } else if (typeof data === 'string' && data) {
      text = data
    }
    if (
      status === 401 &&
      (text.includes('用户不存在') || text.includes('登录已失效') || text.includes('未登录'))
    ) {
      localStorage.removeItem('token')
      if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
        window.location.href = '/login'
      }
    }
    const error = new Error(text)
    error.status = status
    return Promise.reject(error)
  },
)

export default api

export { isBenignEmptyError, isRouteNotFoundError, applyEmptyListFallback, shouldSilenceLoadError, formatApiError, ROUTE_NOT_FOUND_HINT } from '../utils/apiError.js'

export const authApi = {
  login: (phone, password) => api.post('/api/v1/auth/login', { phone, password }),
  sendSmsCode: (phone) => api.post('/api/v1/auth/sms/send', { phone }),
  loginBySms: (phone, code) => api.post('/api/v1/auth/sms/login', { phone, code }),
  register: (data) => api.post('/api/v1/auth/register', data),
  me: () => api.get('/api/v1/auth/me'),
  selectTenant: (tenant_id) => api.post('/api/v1/auth/select-tenant', { tenant_id }),
  switchTenant: (tenant_id) => api.post('/api/v1/auth/switch-tenant', { tenant_id }),
  forgotSendCode: (phone) => api.post('/api/v1/auth/password/forgot/send-code', { phone }),
  forgotReset: (data) => api.post('/api/v1/auth/password/forgot/reset', data),
}

export const llmApi = {
  get: () => api.get('/api/v1/settings/llm'),
  getQuota: () => api.get('/api/v1/settings/llm/quota'),
  update: (data) => api.put('/api/v1/settings/llm', data),
  test: (llmSource = 'tenant') => api.post('/api/v1/settings/llm/test', null, { params: { llm_source: llmSource } }),
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

export const agentApi = {
  createSession: (data) => api.post('/api/v1/agent/sessions', data),
  listSessions: (params) => api.get('/api/v1/agent/sessions', { params }),
  getMessages: (sessionId) => api.get(`/api/v1/agent/sessions/${sessionId}/messages`),
  chat: (sessionId, data) => api.post(`/api/v1/agent/sessions/${sessionId}/chat`, data),
  preflight: (sessionId, data) =>
    api.post(`/api/v1/agent/sessions/${sessionId}/preflight`, data),
  createWorkflow: (data) => api.post('/api/v1/agent/workflows', data),
  getWorkflow: (workflowId) => api.get(`/api/v1/agent/workflows/${workflowId}`),
  resumeWorkflow: (workflowId, data) =>
    api.post(`/api/v1/agent/workflows/${workflowId}/resume`, data),
  listMemories: (params) => api.get('/api/v1/agent/memories', { params }),
  deleteMemory: (memoryId) => api.delete(`/api/v1/agent/memories/${memoryId}`),
  confirmMemory: (memoryId) => api.post(`/api/v1/agent/memories/${memoryId}/confirm`),
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

export const tenantApi = {
  getProfile: () => api.get('/api/v1/tenant/profile'),
  updateProfile: (data) => api.patch('/api/v1/tenant/profile', data),
}

export const teamApi = {
  listRoles: () => api.get('/api/v1/team/roles'),
  createRole: (data) => api.post('/api/v1/team/roles', data),
  updateRole: (id, data) => api.patch(`/api/v1/team/roles/${id}`, data),
  deleteRole: (id) => api.delete(`/api/v1/team/roles/${id}`),
  listMembers: () => api.get('/api/v1/team/members'),
  addMember: (data) => api.post('/api/v1/team/members', data),
  updateMember: (id, data) => api.patch(`/api/v1/team/members/${id}`, data),
  updateMemberRole: (id, role_id) => api.patch(`/api/v1/team/members/${id}/role`, { role_id }),
  disableMember: (id) => api.post(`/api/v1/team/members/${id}/disable`),
}

export const wechatApi = {
  get: () => api.get('/api/v1/settings/wechat'),
  bindMock: (accountName, accountType = 'service') =>
    api.post('/api/v1/settings/wechat/bind-mock', {
      account_name: accountName,
      account_type: accountType,
    }),
}

export const crmApi = {
  listLeads: (params) => api.get('/api/v1/crm/leads', { params }),
  getLead: (id) => api.get(`/api/v1/crm/leads/${id}`),
  createLead: (data) => api.post('/api/v1/crm/leads', data),
  updateLead: (id, data) => api.patch(`/api/v1/crm/leads/${id}`, data),
  deleteLead: (id) => api.delete(`/api/v1/crm/leads/${id}`),
  listCustomers: (params) => api.get('/api/v1/crm/customers', { params }),
  getCustomer: (id) => api.get(`/api/v1/crm/customers/${id}`),
  createCustomer: (data) => api.post('/api/v1/crm/customers', data),
  updateCustomer: (id, data) => api.patch(`/api/v1/crm/customers/${id}`, data),
  deleteCustomer: (id) => api.delete(`/api/v1/crm/customers/${id}`),
  listContacts: (customerId) => api.get(`/api/v1/crm/customers/${customerId}/contacts`),
  createContact: (customerId, data) => api.post(`/api/v1/crm/customers/${customerId}/contacts`, data),
  listActivities: (params) => api.get('/api/v1/crm/activities', { params }),
  createActivity: (data) => api.post('/api/v1/crm/activities', data),
  deleteActivity: (id) => api.delete(`/api/v1/crm/activities/${id}`),
  listTerritories: () => api.get('/api/v1/crm/territories'),
  createTerritory: (data) => api.post('/api/v1/crm/territories', data),
  updateTerritory: (id, data) => api.patch(`/api/v1/crm/territories/${id}`, data),
  deleteTerritory: (id) => api.delete(`/api/v1/crm/territories/${id}`),
  listSalesProfiles: () => api.get('/api/v1/crm/sales-profiles'),
  updateSalesProfile: (membershipId, data) =>
    api.patch(`/api/v1/crm/sales-profiles/${membershipId}`, data),
  listTasks: (params) => api.get('/api/v1/crm/tasks', { params }),
  createTask: (data) => api.post('/api/v1/crm/tasks', data),
  updateTask: (id, data) => api.patch(`/api/v1/crm/tasks/${id}`, data),
  deleteTask: (id) => api.delete(`/api/v1/crm/tasks/${id}`),
  convertLead: (id) => api.post(`/api/v1/crm/leads/${id}/convert`),
  listCampaigns: (params) => api.get('/api/v1/crm/campaigns', { params }),
  getCampaign: (id) => api.get(`/api/v1/crm/campaigns/${id}`),
  createCampaign: (data) => api.post('/api/v1/crm/campaigns', data),
  updateCampaign: (id, data) => api.patch(`/api/v1/crm/campaigns/${id}`, data),
  deleteCampaign: (id) => api.delete(`/api/v1/crm/campaigns/${id}`),
  linkCampaignContent: (campaignId, contentId) =>
    api.post(`/api/v1/crm/campaigns/${campaignId}/contents`, { content_id: contentId }),
  unlinkCampaignContent: (campaignId, contentId) =>
    api.delete(`/api/v1/crm/campaigns/${campaignId}/contents/${contentId}`),
  getSchema: (entityType) => api.get(`/api/v1/crm/schema/${entityType}`),
  createSchemaField: (entityType, data) =>
    api.post(`/api/v1/crm/schema/${entityType}/fields`, data),
  deleteSchemaField: (entityType, fieldKey) =>
    api.delete(`/api/v1/crm/schema/${entityType}/fields/${fieldKey}`),
  getViewPreferences: (entityType) => api.get(`/api/v1/me/view-preferences/${entityType}`),
  saveViewPreferences: (entityType, data) =>
    api.put(`/api/v1/me/view-preferences/${entityType}`, data),
  listViews: (entityType) =>
    api.get(`/api/v1/crm/views${entityType ? `?entity_type=${entityType}` : ''}`),
  createView: (data) => api.post('/api/v1/crm/views', data),
  updateView: (id, data) => api.patch(`/api/v1/crm/views/${id}`, data),
  deleteView: (id) => api.delete(`/api/v1/crm/views/${id}`),
  downloadImportTemplate: async (entityType) => {
    const res = await api.get(`/api/v1/crm/import/template/${entityType}`, { responseType: 'blob' })
    return res.data
  },
  uploadImportJob: async (entityType, file) => {
    const form = new FormData()
    form.append('entity_type', entityType)
    form.append('file', file)
    const { data } = await api.post('/api/v1/crm/import/jobs', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },
  patchImportJob: async (jobId, body) => {
    const { data } = await api.patch(`/api/v1/crm/import/jobs/${jobId}`, body)
    return data
  },
  previewImportJob: async (jobId) => {
    const { data } = await api.post(`/api/v1/crm/import/jobs/${jobId}/preview`)
    return data
  },
  runImportJob: async (jobId) => {
    const { data } = await api.post(`/api/v1/crm/import/jobs/${jobId}/run`)
    return data
  },
  listImportJobs: (params) => api.get('/api/v1/crm/import/jobs', { params }),
  getImportJob: (jobId) => api.get(`/api/v1/crm/import/jobs/${jobId}`),
  downloadImportErrors: async (jobId) => {
    const res = await api.get(`/api/v1/crm/import/jobs/${jobId}/errors`, { responseType: 'blob' })
    return res.data
  },
}

export const adminApi = {
  listContents: (params) => api.get('/api/v1/admin/contents', { params }),
  listTenants: (params) => api.get('/api/v1/admin/tenants', { params }),
  getTenant: (id) => api.get(`/api/v1/admin/tenants/${id}`),
  listTenantMembers: (id) => api.get(`/api/v1/admin/tenants/${id}/members`),
  transferTenantAdmin: (id, new_admin_user_id) =>
    api.post(`/api/v1/admin/tenants/${id}/transfer-admin`, { new_admin_user_id }),
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
  getPlatformLlm: () => api.get('/api/v1/admin/platform-llm'),
  updatePlatformLlm: (data) => api.patch('/api/v1/admin/platform-llm', data),
  testPlatformLlm: (data) => api.post('/api/v1/admin/platform-llm/test', data || {}),
}
