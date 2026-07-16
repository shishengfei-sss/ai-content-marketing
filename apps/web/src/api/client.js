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
  updateActivity: (id, data) => api.patch(`/api/v1/crm/activities/${id}`, data),
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
  convertLead: (id, body = {}) => api.post(`/api/v1/crm/leads/${id}/convert`, body),
  recalculateLeadScore: (id) => api.post(`/api/v1/crm/leads/${id}/recalculate-score`),
  reclaimLeadToPool: (id, body) => api.post(`/api/v1/crm/leads/${id}/reclaim-to-pool`, body),
  listLeadPools: () => api.get('/api/v1/crm/lead-pools'),
  createLeadPool: (data) => api.post('/api/v1/crm/lead-pools', data),
  listLeadPoolLeads: (poolId) => api.get(`/api/v1/crm/lead-pools/${poolId}/leads`),
  claimLeadFromPool: (poolId, leadId) =>
    api.post(`/api/v1/crm/lead-pools/${poolId}/claim`, { lead_id: leadId }),
  listLeadScoringRules: () => api.get('/api/v1/crm/lead-scoring/rules'),
  createLeadScoringRule: (data) => api.post('/api/v1/crm/lead-scoring/rules', data),
  updateLeadScoringRule: (id, data) => api.put(`/api/v1/crm/lead-scoring/rules/${id}`, data),
  deleteLeadScoringRule: (id) => api.delete(`/api/v1/crm/lead-scoring/rules/${id}`),
  listCustomerPools: () => api.get('/api/v1/crm/customer-pools'),
  createCustomerPool: (data) => api.post('/api/v1/crm/customer-pools', data),
  reclaimCustomerToPool: (id, body) => api.post(`/api/v1/crm/customers/${id}/reclaim-to-pool`, body),
  claimCustomerFromPool: (poolId, customerId) =>
    api.post(`/api/v1/crm/customer-pools/${poolId}/claim`, { customer_id: customerId }),
  listAssignmentRules: () => api.get('/api/v1/crm/assignment-rules'),
  createAssignmentRule: (data) => api.post('/api/v1/crm/assignment-rules', data),
  updateAssignmentRule: (id, data) => api.patch(`/api/v1/crm/assignment-rules/${id}`, data),
  deleteAssignmentRule: (id) => api.delete(`/api/v1/crm/assignment-rules/${id}`),
  listAddresses: (params) => api.get('/api/v1/crm/addresses', { params }),
  createAddress: (data) => api.post('/api/v1/crm/addresses', data),
  listTags: () => api.get('/api/v1/crm/tags'),
  createTag: (data) => api.post('/api/v1/crm/tags', data),
  listEntityTags: (params) => api.get('/api/v1/crm/entity-tags', { params }),
  bindEntityTag: (data) => api.post('/api/v1/crm/entity-tags', data),
  listTeamMembers: (params) => api.get('/api/v1/crm/team-members', { params }),
  addTeamMember: (data) => api.post('/api/v1/crm/team-members', data),
  listBant: (leadId) => api.get(`/api/v1/crm/leads/${leadId}/bant`),
  createBant: (leadId, data) => api.post(`/api/v1/crm/leads/${leadId}/bant`, data),
  listNotifications: (params) => api.get('/api/v1/crm/notifications', { params }),
  unreadNotificationCount: () => api.get('/api/v1/crm/notifications/unread-count'),
  markNotificationRead: (id) => api.post(`/api/v1/crm/notifications/${id}/read`),
  markAllNotificationsRead: () => api.post('/api/v1/crm/notifications/read-all'),
  exportLeads: (format = 'csv') =>
    api.get(`/api/v1/crm/export/leads`, { params: { format }, responseType: 'blob' }),
  exportCustomers: (format = 'csv') =>
    api.get(`/api/v1/crm/export/customers`, { params: { format }, responseType: 'blob' }),
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
  // v0.7 报价
  listQuotes: (params) => api.get('/api/v1/crm/quotes', { params }),
  getQuote: (id) => api.get(`/api/v1/crm/quotes/${id}`),
  createQuote: (data) => api.post('/api/v1/crm/quotes', data),
  updateQuote: (id, data) => api.patch(`/api/v1/crm/quotes/${id}`, data),
  deleteQuote: (id) => api.delete(`/api/v1/crm/quotes/${id}`),
  sendQuote: (id) => api.post(`/api/v1/crm/quotes/${id}/send`),
  acceptQuote: (id) => api.post(`/api/v1/crm/quotes/${id}/accept`),
  convertQuoteToOrder: (id) => api.post(`/api/v1/crm/quotes/${id}/convert-to-order`),
  // v0.7 合同
  listContracts: (params) => api.get('/api/v1/crm/contracts', { params }),
  getContract: (id) => api.get(`/api/v1/crm/contracts/${id}`),
  createContract: (data) => api.post('/api/v1/crm/contracts', data),
  updateContract: (id, data) => api.patch(`/api/v1/crm/contracts/${id}`, data),
  deleteContract: (id) => api.delete(`/api/v1/crm/contracts/${id}`),
  signContract: (id, data) => api.post(`/api/v1/crm/contracts/${id}/sign`, data),
  convertContractToOrder: (id) => api.post(`/api/v1/crm/contracts/${id}/convert-to-order`),
  renewContract: (id) => api.post(`/api/v1/crm/contracts/${id}/renew`),
  listContractAmendments: (id) => api.get(`/api/v1/crm/contracts/${id}/amendments`),
  createContractAmendment: (id, data) => api.post(`/api/v1/crm/contracts/${id}/amendments`, data),
  approveContractAmendment: (id) => api.post(`/api/v1/crm/contracts/amendments/${id}/approve`),
  executeContractAmendment: (id) => api.post(`/api/v1/crm/contracts/amendments/${id}/execute`),
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
  updateNumberRule: (entityType, data) =>
    api.put(`/api/v1/crm/number-rules/${entityType}`, data),
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
