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
      if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register') && !window.location.pathname.startsWith('/admin/login')) {
        const isAdminPath = window.location.pathname.startsWith('/admin')
        window.location.href = isAdminPath ? '/admin/login' : '/login'
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
  login: (phone, password, workspaceMode) =>
    api.post('/api/v1/auth/login', {
      phone,
      password,
      workspace_mode: workspaceMode || undefined,
    }),
  sendSmsCode: (phone) => api.post('/api/v1/auth/sms/send', { phone }),
  loginBySms: (phone, code, workspaceMode) =>
    api.post('/api/v1/auth/sms/login', {
      phone,
      code,
      workspace_mode: workspaceMode || undefined,
    }),
  register: (data) => api.post('/api/v1/auth/register', data),
  me: () => api.get('/api/v1/auth/me'),
  selectTenant: (tenant_id) => api.post('/api/v1/auth/select-tenant', { tenant_id }),
  switchTenant: (tenant_id) => api.post('/api/v1/auth/switch-tenant', { tenant_id }),
  switchWorkspace: (workspace_mode) => api.post('/api/v1/auth/switch-workspace', { workspace_mode }),
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
  revise: (id, data) => api.post(`/api/v1/content/${id}/revise`, data),
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
  getSession: (sessionId) => api.get(`/api/v1/agent/sessions/${sessionId}`),
  listSessions: (params) => api.get('/api/v1/agent/sessions', { params }),
  getMessages: (sessionId) => api.get(`/api/v1/agent/sessions/${sessionId}/messages`),
  chat: (sessionId, data) => api.post(`/api/v1/agent/sessions/${sessionId}/chat`, data),
  /**
   * SSE 流式聊天（不走 axios JSON 拦截器）。
   * onEvent(eventName, data)；返回最终 done payload。
   */
  chatStream: async (sessionId, body, { onEvent } = {}) => {
    const base = api.defaults.baseURL || ''
    const token = localStorage.getItem('token')
    const res = await fetch(`${base}/api/v1/agent/sessions/${sessionId}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      let detail = `流式请求失败 (${res.status})`
      try {
        const errBody = await res.json()
        if (typeof errBody?.detail === 'string') detail = errBody.detail
      } catch { /* ignore */ }
      throw new Error(detail)
    }
    const reader = res.body?.getReader()
    if (!reader) throw new Error('浏览器不支持流式响应')
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = 'message'
    let donePayload = null
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n')
      buffer = parts.pop() || ''
      for (const rawLine of parts) {
        const line = rawLine.replace(/\r$/, '')
        if (!line) continue
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim()
          continue
        }
        if (line.startsWith('data:')) {
          const raw = line.slice(5).trim()
          let data
          try {
            data = JSON.parse(raw)
          } catch {
            data = { raw }
          }
          if (currentEvent === 'error') {
            throw new Error(typeof data?.detail === 'string' ? data.detail : '流式生成失败')
          }
          onEvent?.(currentEvent, data)
          if (currentEvent === 'done') donePayload = data
          currentEvent = 'message'
        }
      }
    }
    if (!donePayload) throw new Error('流式结束但未收到完成事件')
    return donePayload
  },
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
  list: (params) => api.get('/api/v1/knowledge/documents', { params }),
  get: (id) => api.get(`/api/v1/knowledge/documents/${id}`),
  update: (id, data) => api.patch(`/api/v1/knowledge/documents/${id}`, data),
  uploadText: (data) => api.post('/api/v1/knowledge/documents/text', data),
  uploadFile: (formData) =>
    api.post('/api/v1/knowledge/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  search: (params) => api.get('/api/v1/knowledge/search', { params }),
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
  enableMember: (id) => api.post(`/api/v1/team/members/${id}/enable`),
  resetMemberPassword: (id, data) => api.post(`/api/v1/team/members/${id}/reset-password`, data),
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
  updateContact: (customerId, contactId, data) =>
    api.patch(`/api/v1/crm/customers/${customerId}/contacts/${contactId}`, data),
  deleteContact: (customerId, contactId) =>
    api.delete(`/api/v1/crm/customers/${customerId}/contacts/${contactId}`),
  listActivities: (params) => api.get('/api/v1/crm/activities', { params }),
  createActivity: (data) => api.post('/api/v1/crm/activities', data),
  updateActivity: (id, data) => api.patch(`/api/v1/crm/activities/${id}`, data),
  deleteActivity: (id) => api.delete(`/api/v1/crm/activities/${id}`),
  listTerritories: () => api.get('/api/v1/crm/territories'),
  createTerritory: (data) => api.post('/api/v1/crm/territories', data),
  updateTerritory: (id, data) => api.patch(`/api/v1/crm/territories/${id}`, data),
  deleteTerritory: (id) => api.delete(`/api/v1/crm/territories/${id}`),
  listSalesProfiles: () => api.get('/api/v1/crm/sales-profiles'),
  updateSalesProfile: (membershipId, data) =>
    api.patch(`/api/v1/crm/sales-profiles/${membershipId}`, data),
  listAssignableOwners: (params) => api.get('/api/v1/crm/assignable-owners', { params }),
  listTasks: (params) => api.get('/api/v1/crm/tasks', { params }),
  createTask: (data) => api.post('/api/v1/crm/tasks', data),
  updateTask: (id, data) => api.patch(`/api/v1/crm/tasks/${id}`, data),
  deleteTask: (id) => api.delete(`/api/v1/crm/tasks/${id}`),
  convertLead: (id, body = {}) => api.post(`/api/v1/crm/leads/${id}/convert`, body),
  recalculateLeadScore: (id) => api.post(`/api/v1/crm/leads/${id}/recalculate-score`),
  reclaimLeadToPool: (id, body) => api.post(`/api/v1/crm/leads/${id}/reclaim-to-pool`, body),
  listLeadPools: () => api.get('/api/v1/crm/lead-pools'),
  createLeadPool: (data) => api.post('/api/v1/crm/lead-pools', data),
  updateLeadPool: (id, data) => api.patch(`/api/v1/crm/lead-pools/${id}`, data),
  deleteLeadPool: (id) => api.delete(`/api/v1/crm/lead-pools/${id}`),
  listLeadPoolLeads: (poolId) => api.get(`/api/v1/crm/lead-pools/${poolId}/leads`),
  claimLeadFromPool: (poolId, leadId) =>
    api.post(`/api/v1/crm/lead-pools/${poolId}/claim`, { lead_id: leadId }),
  listLeadScoringRules: () => api.get('/api/v1/crm/lead-scoring/rules'),
  createLeadScoringRule: (data) => api.post('/api/v1/crm/lead-scoring/rules', data),
  updateLeadScoringRule: (id, data) => api.put(`/api/v1/crm/lead-scoring/rules/${id}`, data),
  deleteLeadScoringRule: (id) => api.delete(`/api/v1/crm/lead-scoring/rules/${id}`),
  listCustomerPools: () => api.get('/api/v1/crm/customer-pools'),
  createCustomerPool: (data) => api.post('/api/v1/crm/customer-pools', data),
  updateCustomerPool: (id, data) => api.patch(`/api/v1/crm/customer-pools/${id}`, data),
  deleteCustomerPool: (id) => api.delete(`/api/v1/crm/customer-pools/${id}`),
  listCustomerPoolCustomers: (poolId) => api.get(`/api/v1/crm/customer-pools/${poolId}/customers`),
  reclaimCustomerToPool: (id, body) => api.post(`/api/v1/crm/customers/${id}/reclaim-to-pool`, body),
  claimCustomerFromPool: (poolId, customerId) =>
    api.post(`/api/v1/crm/customer-pools/${poolId}/claim`, { customer_id: customerId }),
  listAssignmentRules: () => api.get('/api/v1/crm/assignment-rules'),
  createAssignmentRule: (data) => api.post('/api/v1/crm/assignment-rules', data),
  updateAssignmentRule: (id, data) => api.patch(`/api/v1/crm/assignment-rules/${id}`, data),
  deleteAssignmentRule: (id) => api.delete(`/api/v1/crm/assignment-rules/${id}`),
  listAddresses: (params) => api.get('/api/v1/crm/addresses', { params }),
  createAddress: (data) => api.post('/api/v1/crm/addresses', data),
  updateAddress: (id, data) => api.put(`/api/v1/crm/addresses/${id}`, data),
  deleteAddress: (id) => api.delete(`/api/v1/crm/addresses/${id}`),
  listTags: () => api.get('/api/v1/crm/tags'),
  createTag: (data) => api.post('/api/v1/crm/tags', data),
  updateTag: (id, data) => api.patch(`/api/v1/crm/tags/${id}`, data),
  deleteTag: (id) => api.delete(`/api/v1/crm/tags/${id}`),
  listEntityTags: (params) => api.get('/api/v1/crm/entity-tags', { params }),
  bindEntityTag: (data) => api.post('/api/v1/crm/entity-tags', data),
  unbindEntityTag: (params) => api.delete('/api/v1/crm/entity-tags', { params }),
  listTeamMembers: (params) => api.get('/api/v1/crm/team-members', { params }),
  addTeamMember: (data) => api.post('/api/v1/crm/team-members', data),
  listBant: (leadId) => api.get(`/api/v1/crm/leads/${leadId}/bant`),
  createBant: (leadId, data) => api.post(`/api/v1/crm/leads/${leadId}/bant`, data),
  listNotifications: (params) => api.get('/api/v1/crm/notifications', { params }),
  unreadNotificationCount: () => api.get('/api/v1/crm/notifications/unread-count'),
  markNotificationRead: (id) => api.post(`/api/v1/crm/notifications/${id}/read`),
  markAllNotificationsRead: () => api.post('/api/v1/crm/notifications/read-all'),
  exportLeads: (params = {}) =>
    api.get(`/api/v1/crm/export/leads`, {
      params: typeof params === 'string' ? { format: params } : { format: 'csv', ...params },
      responseType: 'blob',
    }),
  exportCustomers: (params = {}) =>
    api.get(`/api/v1/crm/export/customers`, {
      params: typeof params === 'string' ? { format: params } : { format: 'csv', ...params },
      responseType: 'blob',
    }),
  leadFunnel: (params) => api.get('/api/v1/analytics/lead-funnel', { params }),
  salesBoard: () => api.get('/api/v1/analytics/sales-board'),
  sourceRoi: (params) => api.get('/api/v1/analytics/source-roi', { params }),
  lifecycleReport: () => api.get('/api/v1/analytics/lifecycle-report'),
  listNurtureRules: () => api.get('/api/v1/crm/nurture-rules'),
  createNurtureRule: (data) => api.post('/api/v1/crm/nurture-rules', data),
  deleteNurtureRule: (id) => api.delete(`/api/v1/crm/nurture-rules/${id}`),
  runNurtureRules: (params) => api.post('/api/v1/crm/nurture-rules/run', null, { params }),
  getDecisionChain: (customerId) => api.get(`/api/v1/crm/customers/${customerId}/decision-chain`),
  businessLookup: (companyName) =>
    api.get('/api/v1/crm/customers/business-lookup', { params: { company_name: companyName } }),
  listCampaigns: (params) => api.get('/api/v1/crm/campaigns', { params }),
  getCampaign: (id) => api.get(`/api/v1/crm/campaigns/${id}`),
  createCampaign: (data) => api.post('/api/v1/crm/campaigns', data),
  updateCampaign: (id, data) => api.patch(`/api/v1/crm/campaigns/${id}`, data),
  deleteCampaign: (id) => api.delete(`/api/v1/crm/campaigns/${id}`),
  listCampaignChannels: (params) => api.get('/api/v1/crm/campaign-channels', { params }),
  createCampaignChannel: (data) => api.post('/api/v1/crm/campaign-channels', data),
  updateCampaignChannel: (id, data) => api.patch(`/api/v1/crm/campaign-channels/${id}`, data),
  deleteCampaignChannel: (id) => api.delete(`/api/v1/crm/campaign-channels/${id}`),
  seedCampaignChannels: () => api.post('/api/v1/crm/campaign-channels/seed-defaults'),
  linkCampaignContent: (campaignId, contentId) =>
    api.post(`/api/v1/crm/campaigns/${campaignId}/contents`, { content_id: contentId }),
  unlinkCampaignContent: (campaignId, contentId) =>
    api.delete(`/api/v1/crm/campaigns/${campaignId}/contents/${contentId}`),
  listCampaignExecutions: (id) => api.get(`/api/v1/crm/campaigns/${id}/channel-executions`),
  createCampaignExecution: (id, data) => api.post(`/api/v1/crm/campaigns/${id}/channel-executions`, data),
  updateCampaignExecution: (id, data) => api.patch(`/api/v1/crm/campaigns/channel-executions/${id}`, data),
  deleteCampaignExecution: (id) => api.delete(`/api/v1/crm/campaigns/channel-executions/${id}`),
  getCampaignPerformance: (id) => api.get(`/api/v1/crm/campaigns/${id}/performance`),
  listSegments: () => api.get('/api/v1/crm/segments'),
  createSegment: (data) => api.post('/api/v1/crm/segments', data),
  updateSegment: (id, data) => api.patch(`/api/v1/crm/segments/${id}`, data),
  deleteSegment: (id) => api.delete(`/api/v1/crm/segments/${id}`),
  getSchema: (entityType) => api.get(`/api/v1/crm/schema/${entityType}`),
  createSchemaField: (entityType, data) =>
    api.post(`/api/v1/crm/schema/${entityType}/fields`, data),
  updateSchemaField: (entityType, fieldKey, data) =>
    api.patch(`/api/v1/crm/schema/${entityType}/fields/${fieldKey}`, data),
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
  downloadImportTemplate: async (entityType, format = 'xlsx') => {
    const res = await api.get(`/api/v1/crm/import/template/${entityType}`, {
      params: { format },
      responseType: 'blob',
    })
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
  // v0.7 商机与管道
  listDeals: (params) => api.get('/api/v1/crm/deals', { params }),
  getDeal: (id) => api.get(`/api/v1/crm/deals/${id}`),
  createDeal: (data) => api.post('/api/v1/crm/deals', data),
  updateDeal: (id, data) => api.patch(`/api/v1/crm/deals/${id}`, data),
  deleteDeal: (id) => api.delete(`/api/v1/crm/deals/${id}`),
  changeDealStage: (id, data) => api.post(`/api/v1/crm/deals/${id}/stage`, data),
  closeDeal: (id, data) => api.post(`/api/v1/crm/deals/${id}/close`, data),
  listDealStageLogs: (id) => api.get(`/api/v1/crm/deals/${id}/stage-logs`),
  listDealActivities: (id) => api.get(`/api/v1/crm/deals/${id}/activities`),
  createDealActivity: (id, data) => api.post(`/api/v1/crm/deals/${id}/activities`, data),
  // v0.8 P1-02 附件
  listAttachments: (params) => api.get('/api/v1/crm/attachments', { params }),
  uploadAttachment: (entityType, entityId, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/api/v1/crm/attachments', fd, {
      params: { entity_type: entityType, entity_id: entityId },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteAttachment: (id) => api.delete(`/api/v1/crm/attachments/${id}`),
  downloadAttachment: (id) => api.get(`/api/v1/crm/attachments/${id}/download`, { responseType: 'blob' }),
  attachmentDownloadUrl: (id) => `/api/v1/crm/attachments/${id}/download`,
  convertDealToOrder: (id) => api.post(`/api/v1/crm/deals/${id}/convert-to-order`),
  reopenDeal: (id) => api.post(`/api/v1/crm/deals/${id}/reopen`),
  generateDealQuote: (id) => api.post(`/api/v1/crm/deals/${id}/generate-quote`),
  dealFunnel: (params) => api.get('/api/v1/analytics/deal-funnel', { params }),
  dealForecast: (params) => api.get('/api/v1/analytics/deal-forecast', { params }),
  dealWinLoss: (params) => api.get('/api/v1/analytics/deal-win-loss', { params }),
  tradeReport: (params) => api.get('/api/v1/analytics/trade-report', { params }),
  dealStageDuration: (params) => api.get('/api/v1/analytics/deal-stage-duration', { params }),
  batchUpdateDeals: (data) => api.post('/api/v1/crm/deals/batch-update', data),
  cloneDeal: (id) => api.post(`/api/v1/crm/deals/${id}/clone`),
  // v0.8 P1-06 团队
  listDealTeam: (id) => api.get(`/api/v1/crm/deals/${id}/team`),
  addDealTeam: (id, data) => api.post(`/api/v1/crm/deals/${id}/team`, data),
  removeDealTeam: (id, memberId) => api.delete(`/api/v1/crm/deals/${id}/team/${memberId}`),
  listPipelines: () => api.get('/api/v1/crm/pipelines'),
  createPipeline: (data) => api.post('/api/v1/crm/pipelines', data),
  updatePipeline: (id, data) => api.patch(`/api/v1/crm/pipelines/${id}`, data),
  deletePipeline: (id) => api.delete(`/api/v1/crm/pipelines/${id}`),
  createPipelineStage: (pipelineId, data) =>
    api.post(`/api/v1/crm/pipelines/${pipelineId}/stages`, data),
  updatePipelineStage: (pipelineId, stageId, data) =>
    api.patch(`/api/v1/crm/pipelines/${pipelineId}/stages/${stageId}`, data),
  deletePipelineStage: (pipelineId, stageId) =>
    api.delete(`/api/v1/crm/pipelines/${pipelineId}/stages/${stageId}`),
  // v0.7 产品
  listProducts: (params) => api.get('/api/v1/crm/products', { params }),
  listProductCategories: (params) => api.get('/api/v1/crm/product-categories', { params }),
  createProductCategory: (data) => api.post('/api/v1/crm/product-categories', data),
  updateProductCategory: (id, data) => api.patch(`/api/v1/crm/product-categories/${id}`, data),
  deleteProductCategory: (id) => api.delete(`/api/v1/crm/product-categories/${id}`),
  listProductUnits: (params) => api.get('/api/v1/crm/product-units', { params }),
  createProductUnit: (data) => api.post('/api/v1/crm/product-units', data),
  updateProductUnit: (id, data) => api.patch(`/api/v1/crm/product-units/${id}`, data),
  deleteProductUnit: (id) => api.delete(`/api/v1/crm/product-units/${id}`),
  seedProductUnits: () => api.post('/api/v1/crm/product-units/seed-defaults'),
  listProductSpecModels: (params) => api.get('/api/v1/crm/product-spec-models', { params }),
  createProductSpecModel: (data) => api.post('/api/v1/crm/product-spec-models', data),
  updateProductSpecModel: (id, data) => api.patch(`/api/v1/crm/product-spec-models/${id}`, data),
  deleteProductSpecModel: (id) => api.delete(`/api/v1/crm/product-spec-models/${id}`),
  listContractTemplates: (params) => api.get('/api/v1/crm/contract-templates', { params }),
  createContractTemplate: (data) => api.post('/api/v1/crm/contract-templates', data),
  createContractFromTemplate: (data) => api.post('/api/v1/crm/contracts/from-template', data),
  getProduct: (id) => api.get(`/api/v1/crm/products/${id}`),
  createProduct: (data) => api.post('/api/v1/crm/products', data),
  updateProduct: (id, data) => api.patch(`/api/v1/crm/products/${id}`, data),
  deleteProduct: (id) => api.delete(`/api/v1/crm/products/${id}`),
  listProductVariants: (id) => api.get(`/api/v1/crm/products/${id}/variants`),
  createProductVariant: (id, data) => api.post(`/api/v1/crm/products/${id}/variants`, data),
  updateProductVariant: (id, data) => api.patch(`/api/v1/crm/products/variants/${id}`, data),
  deleteProductVariant: (id) => api.delete(`/api/v1/crm/products/variants/${id}`),
  listProductPriceEntries: (id) => api.get(`/api/v1/crm/products/${id}/price-entries`),
  listPriceBooks: () => api.get('/api/v1/crm/price-books'),
  createPriceBook: (data) => api.post('/api/v1/crm/price-books', data),
  updatePriceBook: (id, data) => api.patch(`/api/v1/crm/price-books/${id}`, data),
  deletePriceBook: (id) => api.delete(`/api/v1/crm/price-books/${id}`),
  listPriceBookEntries: (id) => api.get(`/api/v1/crm/price-books/${id}/entries`),
  createPriceBookEntry: (id, data) => api.post(`/api/v1/crm/price-books/${id}/entries`, data),
  deletePriceBookEntry: (id) => api.delete(`/api/v1/crm/price-books/entries/${id}`),
  // v1.3 CPQ
  listCpqProducts: () => api.get('/api/v1/crm/cpq/products'),
  resolveCpqPrice: (data) => api.post('/api/v1/crm/cpq/resolve-price', data),
  calculateCpq: (data) => api.post('/api/v1/crm/cpq/calculate', data),
  createCpqQuote: (data) => api.post('/api/v1/crm/cpq/quotes', data),
  // v1.3 招标线索 L2 + ICP
  getIcpConfig: () => api.get('/api/v1/crm/icp-config'),
  saveIcpConfig: (data) => api.put('/api/v1/crm/icp-config', data),
  listTenderLeads: (params) => api.get('/api/v1/crm/tender-leads', { params }),
  getTenderLead: (id) => api.get(`/api/v1/crm/tender-leads/${id}`),
  claimTenderLead: (id) => api.post(`/api/v1/crm/tender-leads/${id}/claim`),
  ignoreTenderLead: (id) => api.post(`/api/v1/crm/tender-leads/${id}/ignore`),
  getTenderLeadAnalytics: () => api.get('/api/v1/crm/tender-lead-analytics'),
  parseCpqRequirements: (data) => api.post('/api/v1/crm/cpq/ai-parse', data),
  startQuotePdf: (quoteId) => api.post(`/api/v1/crm/cpq/quotes/${quoteId}/pdf`),
  getQuotePdfStatus: (quoteId) => api.get(`/api/v1/crm/cpq/quotes/${quoteId}/pdf-status`),
  downloadQuotePdfUrl: (quoteId) => `/api/v1/crm/cpq/quotes/${quoteId}/pdf/download`,
  cloneQuote: (id) => api.post(`/api/v1/crm/quotes/${id}/clone`),
  listCpqProductParams: (productId, params) =>
    api.get(`/api/v1/crm/cpq/products/${productId}/params`, { params }),
  createCpqProductParam: (productId, data) =>
    api.post(`/api/v1/crm/cpq/products/${productId}/params`, data),
  updateCpqProductParam: (paramId, data) => api.patch(`/api/v1/crm/cpq/params/${paramId}`, data),
  deleteCpqProductParam: (paramId) => api.delete(`/api/v1/crm/cpq/params/${paramId}`),
  createCpqParamPricing: (paramId, data) =>
    api.post(`/api/v1/crm/cpq/params/${paramId}/pricings`, data),
  updateCpqParamPricing: (pricingId, data) =>
    api.patch(`/api/v1/crm/cpq/pricings/${pricingId}`, data),
  deleteCpqParamPricing: (pricingId) => api.delete(`/api/v1/crm/cpq/pricings/${pricingId}`),
  // v0.7 报价
  listQuotes: (params) => api.get('/api/v1/crm/quotes', { params }),
  getQuote: (id) => api.get(`/api/v1/crm/quotes/${id}`),
  createQuote: (data) => api.post('/api/v1/crm/quotes', data),
  updateQuote: (id, data) => api.patch(`/api/v1/crm/quotes/${id}`, data),
  deleteQuote: (id) => api.delete(`/api/v1/crm/quotes/${id}`),
  sendQuote: (id) => api.post(`/api/v1/crm/quotes/${id}/send`),
  acceptQuote: (id) => api.post(`/api/v1/crm/quotes/${id}/accept`),
  rejectQuote: (id, data) => api.post(`/api/v1/crm/quotes/${id}/reject`, data || {}),
  recallQuote: (id) => api.post(`/api/v1/crm/quotes/${id}/recall`),
  convertQuoteToOrder: (id) => api.post(`/api/v1/crm/quotes/${id}/convert-to-order`),
  // v0.7 合同
  listContracts: (params) => api.get('/api/v1/crm/contracts', { params }),
  getContract: (id) => api.get(`/api/v1/crm/contracts/${id}`),
  createContract: (data) => api.post('/api/v1/crm/contracts', data),
  updateContract: (id, data) => api.patch(`/api/v1/crm/contracts/${id}`, data),
  deleteContract: (id) => api.delete(`/api/v1/crm/contracts/${id}`),
  sendContract: (id) => api.post(`/api/v1/crm/contracts/${id}/send`),
  submitContract: (id) => api.post(`/api/v1/crm/contracts/${id}/submit`),
  approveContract: (id) => api.post(`/api/v1/crm/contracts/${id}/approve`),
  rejectContract: (id, data) => api.post(`/api/v1/crm/contracts/${id}/reject`, data),
  withdrawContract: (id) => api.post(`/api/v1/crm/contracts/${id}/withdraw`),
  signContract: (id, data) => api.post(`/api/v1/crm/contracts/${id}/sign`, data),
  activateContract: (id) => api.post(`/api/v1/crm/contracts/${id}/activate`),
  terminateContract: (id) => api.post(`/api/v1/crm/contracts/${id}/terminate`),
  cloneContract: (id) => api.post(`/api/v1/crm/contracts/${id}/clone`),
  renewAsContract: (id) => api.post(`/api/v1/crm/contracts/${id}/renew-contract`),
  convertContractToOrder: (id) => api.post(`/api/v1/crm/contracts/${id}/convert-to-order`),
  batchContractAction: (data) => api.post('/api/v1/crm/contracts/batch-action', data),
  exportContracts: (params = {}) =>
    api.get(`/api/v1/crm/export/contracts`, { params, responseType: 'blob' }),
  renewContract: (id) => api.post(`/api/v1/crm/contracts/${id}/renew`),
  listContractAmendments: (id) => api.get(`/api/v1/crm/contracts/${id}/amendments`),
  createContractAmendment: (id, data) => api.post(`/api/v1/crm/contracts/${id}/amendments`, data),
  approveContractAmendment: (id) => api.post(`/api/v1/crm/contracts/amendments/${id}/approve`),
  executeContractAmendment: (id) => api.post(`/api/v1/crm/contracts/amendments/${id}/execute`),
  createContractFromTemplate: (data) => api.post('/api/v1/crm/contracts/from-template', data),
  // v0.7 订单
  listOrders: (params) => api.get('/api/v1/crm/orders', { params }),
  getOrder: (id) => api.get(`/api/v1/crm/orders/${id}`),
  createOrder: (data) => api.post('/api/v1/crm/orders', data),
  updateOrder: (id, data) => api.patch(`/api/v1/crm/orders/${id}`, data),
  deleteOrder: (id) => api.delete(`/api/v1/crm/orders/${id}`),
  confirmOrder: (id) => api.post(`/api/v1/crm/orders/${id}/confirm`),
  cancelOrder: (id) => api.post(`/api/v1/crm/orders/${id}/cancel`),
  submitOrder: (id) => api.post(`/api/v1/crm/orders/${id}/submit`),
  approveOrder: (id) => api.post(`/api/v1/crm/orders/${id}/approve`),
  rejectOrder: (id, data) => api.post(`/api/v1/crm/orders/${id}/reject`, data),
  withdrawOrder: (id) => api.post(`/api/v1/crm/orders/${id}/withdraw`),
  completeOrder: (id) => api.post(`/api/v1/crm/orders/${id}/complete`),
  cloneOrder: (id, params = {}) => api.post(`/api/v1/crm/orders/${id}/clone`, null, { params }),
  batchOrderAction: (data) => api.post('/api/v1/crm/orders/batch-action', data),
  exportOrders: (params = {}) =>
    api.get(`/api/v1/crm/export/orders`, {
      params,
      responseType: 'blob',
    }),
  listOrderApprovals: (id) => api.get(`/api/v1/crm/orders/${id}/approvals`),
  reviseOrder: (id, data) => api.post(`/api/v1/crm/orders/${id}/revise`, data),
  listOrderRevisions: (id) => api.get(`/api/v1/crm/orders/${id}/revisions`),
  listOrderDeliveries: (id) => api.get(`/api/v1/crm/orders/${id}/deliveries`),
  createOrderDelivery: (id, data) => api.post(`/api/v1/crm/orders/${id}/deliveries`, data),
  shipDelivery: (id) => api.post(`/api/v1/crm/deliveries/${id}/ship`),
  completeDelivery: (id) => api.post(`/api/v1/crm/deliveries/${id}/deliver`),
  deleteDelivery: (id) => api.delete(`/api/v1/crm/deliveries/${id}`),
  listOrderInvoices: (id) => api.get(`/api/v1/crm/orders/${id}/invoices`),
  createOrderInvoice: (id, data) => api.post(`/api/v1/crm/orders/${id}/invoices`, data),
  issueInvoice: (id) => api.post(`/api/v1/crm/invoices/${id}/issue`),
  voidInvoice: (id) => api.post(`/api/v1/crm/invoices/${id}/void`),
  matchInvoicePayment: (id, data) => api.post(`/api/v1/crm/invoices/${id}/payments`, data),
  listInvoicePayments: (id) => api.get(`/api/v1/crm/invoices/${id}/payments`),
  listApprovalRules: () => api.get('/api/v1/crm/approval-rules'),
  // v0.7 回款
  listPayments: (params) => api.get('/api/v1/crm/payments', { params }),
  getPayment: (id) => api.get(`/api/v1/crm/payments/${id}`),
  createPayment: (data) => api.post('/api/v1/crm/payments', data),
  updatePayment: (id, data) => api.patch(`/api/v1/crm/payments/${id}`, data),
  deletePayment: (id) => api.delete(`/api/v1/crm/payments/${id}`),
  confirmPayment: (id) => api.post(`/api/v1/crm/payments/${id}/confirm`),
  reversePayment: (id) => api.post(`/api/v1/crm/payments/${id}/reverse`),
  listOrderPaymentPlans: (orderId) => api.get(`/api/v1/crm/payments/orders/${orderId}/plans`),
  createOrderPaymentPlan: (orderId, data) =>
    api.post(`/api/v1/crm/payments/orders/${orderId}/plans`, data),
  deleteOrderPaymentPlan: (planId) => api.delete(`/api/v1/crm/payments/plans/${planId}`),
  listReceivables: () => api.get('/api/v1/crm/payments/receivables'),
  listOrderRefunds: (orderId) => api.get(`/api/v1/crm/payments/orders/${orderId}/refunds`),
  createRefund: (data) => api.post('/api/v1/crm/payments/refunds', data),
  approveRefund: (id) => api.post(`/api/v1/crm/payments/refunds/${id}/approve`),
  completeRefund: (id) => api.post(`/api/v1/crm/payments/refunds/${id}/complete`),
  rejectRefund: (id) => api.post(`/api/v1/crm/payments/refunds/${id}/reject`),
  // v0.8 编号规则
  listNumberRules: () => api.get('/api/v1/crm/number-rules'),
  createNumberRule: (data) => api.post('/api/v1/crm/number-rules', data),
  updateNumberRule: (entityType, data) =>
    api.put(`/api/v1/crm/number-rules/${entityType}`, data),
  deleteNumberRule: (entityType) => api.delete(`/api/v1/crm/number-rules/${entityType}`),
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
  listShopPermissionAudits: (id, params) =>
    api.get(`/api/v1/admin/users/${id}/shop-permission-audits`, { params }),
  getShopPermissionCatalog: () => api.get('/api/v1/admin/shop/permissions/catalog'),
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
  // v1.3 平台招标线索 L1
  listPlatformTenderLeads: (params) => api.get('/api/v1/admin/platform-tender-leads', { params }),
  createPlatformTenderLead: (data) => api.post('/api/v1/admin/platform-tender-leads', data),
  updatePlatformTenderLead: (id, data) => api.patch(`/api/v1/admin/platform-tender-leads/${id}`, data),
  deletePlatformTenderLead: (id) => api.delete(`/api/v1/admin/platform-tender-leads/${id}`),
  publishPlatformTenderLead: (id) => api.post(`/api/v1/admin/platform-tender-leads/${id}/publish`),
  unpublishPlatformTenderLead: (id) => api.post(`/api/v1/admin/platform-tender-leads/${id}/unpublish`),
  downloadPlatformTenderTemplate: () =>
    api.get('/api/v1/admin/platform-tender-leads/excel-template', { responseType: 'blob' }),
  previewPlatformTenderExcel: (formData) =>
    api.post('/api/v1/admin/platform-tender-leads/excel/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  confirmPlatformTenderExcel: (formData) =>
    api.post('/api/v1/admin/platform-tender-leads/excel/confirm', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  parsePlatformTenderAttachment: (formData) =>
    api.post('/api/v1/admin/platform-tender-leads/parse-attachment', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  parsePlatformTenderText: (data) =>
    api.post('/api/v1/admin/platform-tender-leads/parse-text', data),
  getPlatformTenderParseJob: (id) => api.get(`/api/v1/admin/platform-tender-leads/parse-jobs/${id}`),
  listPlatformTenderParseJobs: (params) =>
    api.get('/api/v1/admin/platform-tender-leads/parse-jobs', { params }),
  confirmPlatformTenderParseJob: (id, data) =>
    api.post(`/api/v1/admin/platform-tender-leads/parse-jobs/${id}/confirm`, data),
  // 内容获客商城 · 平台端
  listShopMerchants: (params) => api.get('/api/v1/admin/shop/merchants', { params }),
  exportShopMerchants: (params) =>
    api.get('/api/v1/admin/shop/merchants/export', { params, responseType: 'blob' }),
  createShopMerchantExport: (data) => api.post('/api/v1/admin/shop/merchants/export', data),
  getShopMerchantExportFile: (id) =>
    api.get(`/api/v1/admin/shop/merchants/export-tasks/${id}/file`, { responseType: 'blob' }),
  getShopMerchant: (tenantId) => api.get(`/api/v1/admin/shop/merchants/${tenantId}`),
  listShopMerchantServiceLogs: (tenantId, params) =>
    api.get(`/api/v1/admin/shop/merchants/${tenantId}/service-logs`, { params }),
  createShopServiceNote: (tenantId, data) =>
    api.post(`/api/v1/admin/shop/merchants/${tenantId}/service-logs/notes`, data),
  createShopRenewalRequest: (tenantId, data) =>
    api.post(`/api/v1/admin/shop/merchants/${tenantId}/service-logs/renewal-requests`, data),
  getShopMerchantSubscriptions: (tenantId) =>
    api.get(`/api/v1/admin/shop/merchants/${tenantId}/subscriptions`),
  getShopMerchantEntitlements: (tenantId, params) =>
    api.get(`/api/v1/admin/shop/merchants/${tenantId}/entitlements`, { params }),
  listShopFeatureDictionary: (params) =>
    api.get('/api/v1/admin/shop/feature-dictionary', { params }),
  previewShopFeatureCode: () => api.post('/api/v1/admin/shop/feature-dictionary/preview-code'),
  createShopFeature: (data) => api.post('/api/v1/admin/shop/feature-dictionary', data),
  getShopFeature: (id) => api.get(`/api/v1/admin/shop/feature-dictionary/${id}`),
  updateShopFeature: (id, data) => api.patch(`/api/v1/admin/shop/feature-dictionary/${id}`, data),
  deactivateShopFeature: (id, data) =>
    api.post(`/api/v1/admin/shop/feature-dictionary/${id}/deactivate`, data || {}),
  activateShopFeature: (id) => api.post(`/api/v1/admin/shop/feature-dictionary/${id}/activate`),
  suspendShopMerchant: (tenantId, data) =>
    api.post(`/api/v1/admin/shop/merchants/${tenantId}/suspend`, data),
  resumeShopMerchant: (tenantId, data) =>
    api.post(`/api/v1/admin/shop/merchants/${tenantId}/resume`, data || {}),
  closeShopMerchant: (tenantId, data) =>
    api.post(`/api/v1/admin/shop/merchants/${tenantId}/close`, data),
  listShopCsUsers: () => api.get('/api/v1/admin/shop/cs-users'),
  assignShopMerchant: (tenantId, data) =>
    api.post(`/api/v1/admin/shop/merchants/${tenantId}/assign`, data),
  batchAssignShopMerchants: (data) =>
    api.post('/api/v1/admin/shop/merchants/batch-assign', data),
  listShopMerchantTags: (params) => api.get('/api/v1/admin/shop/merchant-tags', { params }),
  putShopMerchantTags: (tenantId, data) =>
    api.put(`/api/v1/admin/shop/merchants/${tenantId}/tags`, data),
  revealShopMerchantSensitive: (tenantId, data) =>
    api.post(`/api/v1/admin/shop/merchants/${tenantId}/reveal-sensitive`, data || {}),
  listShopPlanTemplates: (params) => api.get('/api/v1/admin/shop/plan-templates', { params }),
  previewShopPlanCode: () => api.post('/api/v1/admin/shop/plan-templates/preview-code'),
  createShopPlanTemplate: (data) => api.post('/api/v1/admin/shop/plan-templates', data),
  getShopPlanTemplate: (code) => api.get(`/api/v1/admin/shop/plan-templates/${code}`),
  updateShopPlanTemplate: (code, data) => api.patch(`/api/v1/admin/shop/plan-templates/${code}`, data),
  publishShopPlanTemplate: (code) => api.post(`/api/v1/admin/shop/plan-templates/${code}/publish`),
  unpublishShopPlanTemplate: (code) => api.post(`/api/v1/admin/shop/plan-templates/${code}/unpublish`),
  listShopSubscriptions: (params) => api.get('/api/v1/admin/shop/subscriptions', { params }),
  exportShopSubscriptions: (params) =>
    api.get('/api/v1/admin/shop/subscriptions/export', { params, responseType: 'blob' }),
  createShopSubscriptionExport: (data) =>
    api.post('/api/v1/admin/shop/subscriptions/export', data || {}),
  getShopSubscriptionExportFile: (id) =>
    api.get(`/api/v1/admin/shop/subscriptions/export-tasks/${id}/file`, { responseType: 'blob' }),
  createShopSubscription: (data) => api.post('/api/v1/admin/shop/subscriptions', data),
  getShopSubscription: (id) => api.get(`/api/v1/admin/shop/subscriptions/${id}`),
  replaceShopSubscription: (id, data) =>
    api.post(`/api/v1/admin/shop/subscriptions/${id}/replace`, data),
  renewShopSubscription: (id, data) =>
    api.post(`/api/v1/admin/shop/subscriptions/${id}/renew`, data),
  cancelShopSubscription: (id, data) =>
    api.post(`/api/v1/admin/shop/subscriptions/${id}/cancel`, data || {}),
  listShopPendingRenewals: () => api.get('/api/v1/admin/shop/merchants/pending-renewals'),
  cancelShopRenewalRequest: (tenantId, logId, note) =>
    api.post(
      `/api/v1/admin/shop/merchants/${tenantId}/service-logs/renewal-requests/${logId}/cancel`,
      {},
      { params: { note } },
    ),
  markShopRenewalProcessing: (tenantId, logId) =>
    api.post(
      `/api/v1/admin/shop/merchants/${tenantId}/service-logs/renewal-requests/${logId}/mark-processing`,
    ),
  revertShopRenewalPending: (tenantId, logId) =>
    api.post(
      `/api/v1/admin/shop/merchants/${tenantId}/service-logs/renewal-requests/${logId}/revert-pending`,
    ),
  listShopOnboardingApplications: (params) =>
    api.get('/api/v1/admin/shop/onboarding/applications', { params }),
  getShopOnboardingApplication: (id) =>
    api.get(`/api/v1/admin/shop/onboarding/applications/${id}`),
  revealShopOnboardingSensitive: (applicationId, data) =>
    api.post(
      `/api/v1/admin/shop/onboarding/applications/${applicationId}/reveal-sensitive`,
      data || {},
    ),
  listShopOnboardingRejectReasons: () =>
    api.get('/api/v1/admin/shop/onboarding/reject-reasons'),
  listShopOnboardingApproveOptions: (params) =>
    api.get('/api/v1/admin/shop/onboarding/approve-options', { params }),
  downloadShopOnboardingFile: (applicationId, fileId) =>
    api.get(`/api/v1/admin/shop/onboarding/applications/${applicationId}/files/${fileId}`, {
      responseType: 'blob',
    }),
  listShopOnboardingTenantOptions: (params) =>
    api.get('/api/v1/admin/shop/onboarding/tenant-options', { params }),
  getShopOnboardingPrefill: (tenantId) =>
    api.get(`/api/v1/admin/shop/onboarding/tenants/${tenantId}/prefill`),
  createShopOnboardingApplication: (data) =>
    api.post('/api/v1/admin/shop/onboarding/applications', data),
  approveShopOnboarding: (id, data) =>
    api.post(`/api/v1/admin/shop/onboarding/applications/${id}/approve`, data),
  rejectShopOnboarding: (id, data) =>
    api.post(`/api/v1/admin/shop/onboarding/applications/${id}/reject`, data),
  uploadShopOnboardingFile: (tenantId, docType, file) => {
    const fd = new FormData()
    fd.append('tenant_id', tenantId)
    fd.append('doc_type', docType)
    fd.append('file', file)
    return api.post('/api/v1/admin/shop/onboarding/files', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  shopOnboardingOcr: (data) => api.post('/api/v1/admin/shop/onboarding/ocr', data),
  listShopPaymentOnboarding: (params) =>
    api.get('/api/v1/admin/shop/payment-onboarding', { params }),
  exportShopPaymentOnboarding: (params) =>
    api.get('/api/v1/admin/shop/payment-onboarding/export', { params, responseType: 'blob' }),
  createShopPaymentOnboardingExport: (data) =>
    api.post('/api/v1/admin/shop/payment-onboarding/export', data || {}),
  getShopPaymentOnboardingExportFile: (id) =>
    api.get(`/api/v1/admin/shop/payment-onboarding/export-tasks/${id}/file`, { responseType: 'blob' }),
  getShopPaymentOnboarding: (tenantId) =>
    api.get(`/api/v1/admin/shop/payment-onboarding/${tenantId}`),
  getShopChannelConfig: () => api.get('/api/v1/admin/shop/payment-onboarding/channel-config'),
  saveShopDoudianConfig: (data) =>
    api.put('/api/v1/admin/shop/payment-onboarding/channel-config/doudian', data || {}),
  rotateShopDoudianSecret: (data) =>
    api.post('/api/v1/admin/shop/payment-onboarding/channel-config/doudian/rotate', data || {}),
  testShopDoudianConfig: () =>
    api.post('/api/v1/admin/shop/payment-onboarding/channel-config/doudian/test'),
  saveShopWechatPayConfig: (data) =>
    api.put('/api/v1/admin/shop/payment-onboarding/channel-config/wechat-pay', data || {}),
  rotateShopWechatCert: (data) =>
    api.post('/api/v1/admin/shop/payment-onboarding/channel-config/wechat-pay/rotate-cert', data || {}),
  rotateShopWechatV3: (data) =>
    api.post('/api/v1/admin/shop/payment-onboarding/channel-config/wechat-pay/rotate-v3', data || {}),
  testShopWechatPayConfig: () =>
    api.post('/api/v1/admin/shop/payment-onboarding/channel-config/wechat-pay/test'),
  refreshShopPaymentOnboarding: (tenantId) =>
    api.post(`/api/v1/admin/shop/payment-onboarding/${tenantId}/refresh`),
  submitShopPaymentWechat: (tenantId) =>
    api.post(`/api/v1/admin/shop/payment-onboarding/${tenantId}/submit-wechat`),
  approveShopPaymentOnboarding: (tenantId, data) =>
    api.post(`/api/v1/admin/shop/payment-onboarding/${tenantId}/approve`, data),
  rejectShopPaymentOnboarding: (tenantId, data) =>
    api.post(`/api/v1/admin/shop/payment-onboarding/${tenantId}/reject`, data),
  revealShopPaymentSensitive: (tenantId) =>
    api.post(`/api/v1/admin/shop/payment-onboarding/${tenantId}/reveal-sensitive`),
  notifyShopPaymentMerchant: (tenantId) =>
    api.post(`/api/v1/admin/shop/payment-onboarding/${tenantId}/notify`),
  getShopSmsChannelConfig: () => api.get('/api/v1/admin/shop/sms/channel-config'),
  saveShopSmsChannelConfig: (data) => api.put('/api/v1/admin/shop/sms/channel-config', data || {}),
  testShopSmsChannelConfig: () => api.post('/api/v1/admin/shop/sms/channel-config/test'),
  listShopSmsMerchants: () => api.get('/api/v1/admin/shop/sms/merchant-options'),
  listShopSmsSignatures: (params) => api.get('/api/v1/admin/shop/sms/signatures', { params }),
  exportShopSmsSignatures: (params) =>
    api.get('/api/v1/admin/shop/sms/signatures/export', { params, responseType: 'blob' }),
  createShopSmsSignatureExport: (data) =>
    api.post('/api/v1/admin/shop/sms/signatures/export', data || {}),
  getShopSmsSignatureExportFile: (id) =>
    api.get(`/api/v1/admin/shop/sms/signatures/export-tasks/${id}/file`, { responseType: 'blob' }),
  createShopSmsSignature: (data) => api.post('/api/v1/admin/shop/sms/signatures', data),
  getShopSmsSignature: (id) => api.get(`/api/v1/admin/shop/sms/signatures/${id}`),
  syncShopSmsSignature: (id) => api.post(`/api/v1/admin/shop/sms/signatures/${id}/sync`),
  withdrawShopSmsSignature: (id) => api.post(`/api/v1/admin/shop/sms/signatures/${id}/withdraw`),
  approveShopSmsSignature: (id) => api.post(`/api/v1/admin/shop/sms/signatures/${id}/approve`),
  rejectShopSmsSignature: (id, data) =>
    api.post(`/api/v1/admin/shop/sms/signatures/${id}/reject`, data),
  resubmitShopSmsSignature: (id, data) =>
    api.post(`/api/v1/admin/shop/sms/signatures/${id}/resubmit`, data),
  listShopSmsTemplates: (params) => api.get('/api/v1/admin/shop/sms/templates', { params }),
  exportShopSmsTemplates: (params) =>
    api.get('/api/v1/admin/shop/sms/templates/export', { params, responseType: 'blob' }),
  createShopSmsTemplateExport: (data) =>
    api.post('/api/v1/admin/shop/sms/templates/export', data || {}),
  getShopSmsTemplateExportFile: (id) =>
    api.get(`/api/v1/admin/shop/sms/templates/export-tasks/${id}/file`, { responseType: 'blob' }),
  createShopSmsTemplate: (data) => api.post('/api/v1/admin/shop/sms/templates', data),
  updateShopSmsTemplate: (id, data) => api.patch(`/api/v1/admin/shop/sms/templates/${id}`, data),
  setDefaultShopSmsTemplate: (id) => api.post(`/api/v1/admin/shop/sms/templates/${id}/set-default`),
  listShopSmsAssignments: (params) => api.get('/api/v1/admin/shop/sms/assignments', { params }),
  exportShopSmsAssignments: (params) =>
    api.get('/api/v1/admin/shop/sms/assignments/export', { params, responseType: 'blob' }),
  createShopSmsAssignmentExport: (data) =>
    api.post('/api/v1/admin/shop/sms/assignments/export', data || {}),
  getShopSmsAssignmentExportFile: (id) =>
    api.get(`/api/v1/admin/shop/sms/assignments/export-tasks/${id}/file`, { responseType: 'blob' }),
  getShopSmsAssignOptions: (tenantId) =>
    api.get('/api/v1/admin/shop/sms/assignments/options', { params: { tenant_id: tenantId } }),
  assignShopSms: (data) => api.post('/api/v1/admin/shop/sms/assignments', data),
  listShopSmsLogs: (params) => api.get('/api/v1/admin/shop/sms/logs', { params }),
  exportShopSmsLogs: (params) =>
    api.get('/api/v1/admin/shop/sms/logs/export', { params, responseType: 'blob' }),
  createShopSmsLogExport: (data) => api.post('/api/v1/admin/shop/sms/logs/export', data || {}),
  getShopSmsLogExportFile: (id) =>
    api.get(`/api/v1/admin/shop/sms/logs/export-tasks/${id}/file`, { responseType: 'blob' }),
  getShopSmsLog: (id) => api.get(`/api/v1/admin/shop/sms/logs/${id}`),
  revealShopSmsMobile: (id) => api.post(`/api/v1/admin/shop/sms/logs/${id}/reveal-mobile`),
  retryShopSmsLog: (id) => api.post(`/api/v1/admin/shop/sms/logs/${id}/retry`),
  getShopAnalyticsSummary: () => api.get('/api/v1/admin/shop/analytics/summary'),
  getShopAnalyticsTrends: (params) => api.get('/api/v1/admin/shop/analytics/trends', { params }),
  exportShopAnalyticsDaily: (data) =>
    api.post('/api/v1/admin/shop/analytics/export-daily', data || {}, { responseType: 'blob' }),
  listShopSettlementBatches: (params) => api.get('/api/v1/admin/shop/settlement-batches', { params }),
  exportShopSettlementBatches: (params) =>
    api.get('/api/v1/admin/shop/settlement-batches/export', { params, responseType: 'blob' }),
  createShopSettlementExport: (data) =>
    api.post('/api/v1/admin/shop/settlement-batches/export', data || {}),
  getShopSettlementExportFile: (id) =>
    api.get(`/api/v1/admin/shop/settlement-batches/export-tasks/${id}/file`, { responseType: 'blob' }),
  getShopSettlementBatch: (id) => api.get(`/api/v1/admin/shop/settlement-batches/${id}`),
  confirmShopSettlement: (id, data) =>
    api.post(`/api/v1/admin/shop/settlement-batches/${id}/confirm`, data || {}),
  retryShopSettlement: (id, data) =>
    api.post(`/api/v1/admin/shop/settlement-batches/${id}/retry`, data),
  uploadShopSettlementVoucher: (id, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post(`/api/v1/admin/shop/settlement-batches/${id}/voucher`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  downloadShopSettlementVoucher: (id, fileId) =>
    api.get(`/api/v1/admin/shop/settlement-batches/${id}/voucher/${fileId}`, { responseType: 'blob' }),
  exportShopSettlementVoucher: (id) =>
    api.get(`/api/v1/admin/shop/settlement-batches/${id}/export`, { responseType: 'blob' }),
  exportShopSettlementItems: (id) =>
    api.get(`/api/v1/admin/shop/settlement-batches/${id}/export-items`, { responseType: 'blob' }),
  listShopModerationCases: (params) => api.get('/api/v1/admin/shop/moderation-cases', { params }),
  getShopModerationSummary: () => api.get('/api/v1/admin/shop/moderation-cases/summary'),
  exportShopModerationCases: (params) =>
    api.get('/api/v1/admin/shop/moderation-cases/export', { params, responseType: 'blob' }),
  createShopModerationExport: (data) =>
    api.post('/api/v1/admin/shop/moderation-cases/export', data || {}),
  getShopModerationExportFile: (id) =>
    api.get(`/api/v1/admin/shop/moderation-cases/export-tasks/${id}/file`, { responseType: 'blob' }),
  getShopModerationCase: (id) => api.get(`/api/v1/admin/shop/moderation-cases/${id}`),
  downloadShopModerationAttachment: (id, fileId) =>
    api.get(`/api/v1/admin/shop/moderation-cases/${id}/attachments/${fileId}`, { responseType: 'blob' }),
  takeShopModerationCase: (id) => api.post(`/api/v1/admin/shop/moderation-cases/${id}/take`),
  forceOffShopModerationCase: (id, data) =>
    api.post(`/api/v1/admin/shop/moderation-cases/${id}/force-off-sale`, data || {}),
  closeShopModerationCase: (id, data) =>
    api.post(`/api/v1/admin/shop/moderation-cases/${id}/close`, data || {}),
  listShopProductReviews: (params) => api.get('/api/v1/admin/shop/product-reviews', { params }),
  getShopProductReview: (id) => api.get(`/api/v1/admin/shop/product-reviews/${id}`),
  getShopProductReviewCover: (id) =>
    api.get(`/api/v1/admin/shop/product-reviews/${id}/snapshot-cover`, { responseType: 'blob' }),
  getShopProductReviewLesson: (reviewId, lessonId) =>
    api.get(`/api/v1/admin/shop/product-reviews/${reviewId}/lessons/${lessonId}`),
  getShopProductReviewLessonMedia: (reviewId, lessonId, params) =>
    api.get(`/api/v1/admin/shop/product-reviews/${reviewId}/lessons/${lessonId}/media`, {
      params,
      responseType: 'blob',
    }),
  getShopProductReviewRefAsset: (reviewId, fileId, params) =>
    api.get(`/api/v1/admin/shop/product-reviews/${reviewId}/ref-assets/${fileId}`, {
      params,
      responseType: 'blob',
    }),
  getShopProductReviewRefAssetHtmlPreview: (reviewId, fileId) =>
    api.get(`/api/v1/admin/shop/product-reviews/${reviewId}/ref-assets/${fileId}/html-preview`, {
      responseType: 'text',
    }),
  getShopProductReviewBuyerPreview: (id) =>
    api.get(`/api/v1/admin/shop/product-reviews/${id}/buyer-preview`),
  approveShopProductReview: (id, data) =>
    api.post(`/api/v1/admin/shop/product-reviews/${id}/approve`, data || {}),
  rejectShopProductReview: (id, data) =>
    api.post(`/api/v1/admin/shop/product-reviews/${id}/reject`, data),
  forceOffShopProductReview: (id, data) =>
    api.post(`/api/v1/admin/shop/product-reviews/${id}/force-off-sale`, data),
  listShopNumberRules: () => api.get('/api/v1/admin/shop/number-rules'),
  updateShopNumberRule: (entityType, data) =>
    api.put(`/api/v1/admin/shop/number-rules/${entityType}`, data),
  previewShopNumberRule: (entityType, data) =>
    api.post(`/api/v1/admin/shop/number-rules/${entityType}/preview`, data || {}),
  resetShopNumberRules: () => api.post('/api/v1/admin/shop/number-rules/reset-defaults'),
}

/** 内容获客商城 · 商家端（智营壳内 A20） */
export const shopApi = {
  getOnboardingStatus: () => api.get('/api/v1/shop/onboarding/status'),
  submitOnboarding: (data) => api.post('/api/v1/shop/onboarding/applications', data),
  resubmitOnboarding: (id, data) => api.put(`/api/v1/shop/onboarding/applications/${id}`, data),
  uploadOnboardingFile: (docType, file) => {
    const fd = new FormData()
    fd.append('doc_type', docType)
    fd.append('file', file)
    return api.post('/api/v1/shop/onboarding/files', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  downloadOnboardingFile: (fileId) =>
    api.get(`/api/v1/shop/onboarding/files/${fileId}`, { responseType: 'blob' }),
  onboardingOcr: (data) => api.post('/api/v1/shop/onboarding/ocr', data),
}
