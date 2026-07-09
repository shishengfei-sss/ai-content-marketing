const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export { BASE_URL }

function buildCrmQuery(params = {}) {
  const sp = new URLSearchParams()
  for (const [key, val] of Object.entries(params)) {
    if (val === undefined || val === null || val === '') continue
    sp.append(key, typeof val === 'object' ? JSON.stringify(val) : String(val))
  }
  const qs = sp.toString()
  return qs ? `?${qs}` : ''
}

function getToken() {
  return uni.getStorageSync('ai_marketing_token') || ''
}

export async function request(options) {
  const { url, method = 'GET', data } = options
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE_URL + url,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        Authorization: getToken() ? `Bearer ${getToken()}` : '',
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          const detail = res.data?.detail || '请求失败'
          const error = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
          error.status = res.statusCode
          reject(error)
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络错误'))
      },
    })
  })
}

export const authApi = {
  login: (phone, password) =>
    request({ url: '/api/v1/auth/login', method: 'POST', data: { phone, password } }),
  sendSmsCode: (phone) =>
    request({ url: '/api/v1/auth/sms/send', method: 'POST', data: { phone } }),
  loginBySms: (phone, code) =>
    request({ url: '/api/v1/auth/sms/login', method: 'POST', data: { phone, code } }),
  register: (payload) =>
    request({ url: '/api/v1/auth/register', method: 'POST', data: payload }),
  me: () => request({ url: '/api/v1/auth/me' }),
  selectTenant: (tenant_id) =>
    request({ url: '/api/v1/auth/select-tenant', method: 'POST', data: { tenant_id } }),
  switchTenant: (tenant_id) =>
    request({ url: '/api/v1/auth/switch-tenant', method: 'POST', data: { tenant_id } }),
  forgotSendCode: (phone) =>
    request({ url: '/api/v1/auth/password/forgot/send-code', method: 'POST', data: { phone } }),
  forgotReset: (payload) =>
    request({ url: '/api/v1/auth/password/forgot/reset', method: 'POST', data: payload }),
}

export const tenantApi = {
  getProfile: () => request({ url: '/api/v1/tenant/profile' }),
  updateProfile: (data) => request({ url: '/api/v1/tenant/profile', method: 'PATCH', data }),
}

export const teamApi = {
  listMembers: () => request({ url: '/api/v1/team/members' }),
  listRoles: () => request({ url: '/api/v1/team/roles' }),
  addMember: (data) => request({ url: '/api/v1/team/members', method: 'POST', data }),
  updateMemberRole: (id, role_id) =>
    request({ url: `/api/v1/team/members/${id}/role`, method: 'PATCH', data: { role_id } }),
  disableMember: (id) =>
    request({ url: `/api/v1/team/members/${id}/disable`, method: 'POST' }),
  createRole: (data) => request({ url: '/api/v1/team/roles', method: 'POST', data }),
  updateRole: (id, data) => request({ url: `/api/v1/team/roles/${id}`, method: 'PATCH', data }),
  deleteRole: (id) => request({ url: `/api/v1/team/roles/${id}`, method: 'DELETE' }),
}

export const brandApi = {
  getUserPrompt: () => request({ url: '/api/v1/settings/user-prompt' }),
  updateUserPrompt: (global_instructions) =>
    request({
      url: '/api/v1/settings/user-prompt',
      method: 'PUT',
      data: { global_instructions },
    }),
}

export const llmApi = {
  getQuota: () => request({ url: '/api/v1/settings/llm/quota' }),
}

export const dashboardApi = {
  stats: () => request({ url: '/api/v1/dashboard/stats' }),
}

export const analyticsApi = {
  stats: () => request({ url: '/api/v1/analytics/stats' }),
}

export const contentApi = {
  get: (id) => request({ url: `/api/v1/content/${id}` }),
  list: (params) => {
    const query = new URLSearchParams(params).toString()
    return request({ url: `/api/v1/content${query ? `?${query}` : ''}` })
  },
  calendar: () => request({ url: '/api/v1/content/calendar' }),
  proposals: (payload) =>
    request({ url: '/api/v1/content/proposals', method: 'POST', data: payload }),
  generate: (payload) =>
    request({ url: '/api/v1/content/generate', method: 'POST', data: payload }),
  publish: (id) => request({ url: `/api/v1/content/${id}/publish`, method: 'POST' }),
  retryPublish: (id) =>
    request({ url: `/api/v1/content/${id}/retry-publish`, method: 'POST' }),
  exportXhs: (id) => request({ url: `/api/v1/content/${id}/export/xhs`, method: 'POST' }),
  exportDouyin: (id) =>
    request({ url: `/api/v1/content/${id}/export/douyin`, method: 'POST' }),
  exportScript: (id) =>
    request({ url: `/api/v1/content/${id}/export/script`, method: 'POST' }),
}

export const agentApi = {
  createSession: (data) => request({ url: '/api/v1/agent/sessions', method: 'POST', data }),
  listSessions: (params) =>
    request({ url: '/api/v1/agent/sessions', method: 'GET', data: params }),
  getMessages: (sessionId) => request({ url: `/api/v1/agent/sessions/${sessionId}/messages` }),
  chat: (sessionId, data) =>
    request({ url: `/api/v1/agent/sessions/${sessionId}/chat`, method: 'POST', data }),
  preflight: (sessionId, data) =>
    request({ url: `/api/v1/agent/sessions/${sessionId}/preflight`, method: 'POST', data }),
  createWorkflow: (data) => request({ url: '/api/v1/agent/workflows', method: 'POST', data }),
  getWorkflow: (workflowId) => request({ url: `/api/v1/agent/workflows/${workflowId}` }),
  resumeWorkflow: (workflowId, data) =>
    request({ url: `/api/v1/agent/workflows/${workflowId}/resume`, method: 'POST', data }),
  listMemories: (params) => request({ url: '/api/v1/agent/memories', data: params }),
  deleteMemory: (memoryId) =>
    request({ url: `/api/v1/agent/memories/${memoryId}`, method: 'DELETE' }),
  confirmMemory: (memoryId) =>
    request({ url: `/api/v1/agent/memories/${memoryId}/confirm`, method: 'POST' }),
}

export const wechatApi = {
  get: () => request({ url: '/api/v1/settings/wechat' }),
  bindMock: (accountName, accountType = 'service') =>
    request({
      url: '/api/v1/settings/wechat/bind-mock',
      method: 'POST',
      data: { account_name: accountName, account_type: accountType },
    }),
}

export const assistantsApi = {
  list: () => request({ url: '/api/v1/assistants' }),
}

export const templatesApi = {
  list: (params) => request({ url: '/api/v1/templates', data: params }),
}

export const crmApi = {
  listLeads: (params) => request({ url: `/api/v1/crm/leads${buildCrmQuery(params)}` }),
  getLead: (id) => request({ url: `/api/v1/crm/leads/${id}` }),
  createLead: (data) => request({ url: '/api/v1/crm/leads', method: 'POST', data }),
  updateLead: (id, data) => request({ url: `/api/v1/crm/leads/${id}`, method: 'PATCH', data }),
  convertLead: (id) => request({ url: `/api/v1/crm/leads/${id}/convert`, method: 'POST' }),
  updateCustomer: (id, data) => request({ url: `/api/v1/crm/customers/${id}`, method: 'PATCH', data }),
  listViews: (entityType) => request({ url: `/api/v1/crm/views?entity_type=${entityType}` }),
  listCampaigns: (params) => {
    const query = new URLSearchParams(params).toString()
    return request({ url: `/api/v1/crm/campaigns${query ? `?${query}` : ''}` })
  },
  getCampaign: (id) => request({ url: `/api/v1/crm/campaigns/${id}` }),
  listCustomers: (params) => request({ url: `/api/v1/crm/customers${buildCrmQuery(params)}` }),
  getCustomer: (id) => request({ url: `/api/v1/crm/customers/${id}` }),
  listContacts: (customerId) => request({ url: `/api/v1/crm/customers/${customerId}/contacts` }),
  createCustomer: (data) => request({ url: '/api/v1/crm/customers', method: 'POST', data }),
  listActivities: (params) => {
    const query = new URLSearchParams(params).toString()
    return request({ url: `/api/v1/crm/activities${query ? `?${query}` : ''}` })
  },
  createActivity: (data) => request({ url: '/api/v1/crm/activities', method: 'POST', data }),
  listTasks: (params) => {
    const query = new URLSearchParams(params).toString()
    return request({ url: `/api/v1/crm/tasks${query ? `?${query}` : ''}` })
  },
  createTask: (data) => request({ url: '/api/v1/crm/tasks', method: 'POST', data }),
  updateTask: (id, data) => request({ url: `/api/v1/crm/tasks/${id}`, method: 'PATCH', data }),
  getSchema: (entityType) => request({ url: `/api/v1/crm/schema/${entityType}` }),
  getViewPreferences: (entityType) => request({ url: `/api/v1/me/view-preferences/${entityType}` }),
  saveViewPreferences: (entityType, data) =>
    request({ url: `/api/v1/me/view-preferences/${entityType}`, method: 'PUT', data }),
}
