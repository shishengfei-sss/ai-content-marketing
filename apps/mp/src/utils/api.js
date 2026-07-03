const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001'

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
          reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)))
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络错误'))
      },
    })
  })
}

export const authApi = {
  login: (email, password) =>
    request({ url: '/api/v1/auth/login', method: 'POST', data: { email, password } }),
  me: () => request({ url: '/api/v1/auth/me' }),
}

export const dashboardApi = {
  stats: () => request({ url: '/api/v1/dashboard/stats' }),
}

export const contentApi = {
  list: (params) => {
    const query = new URLSearchParams(params).toString()
    return request({ url: `/api/v1/content${query ? `?${query}` : ''}` })
  },
  calendar: () => request({ url: '/api/v1/content/calendar' }),
  generate: (payload) =>
    request({ url: '/api/v1/content/generate', method: 'POST', data: payload }),
  submitReview: (id, comment = '') =>
    request({ url: `/api/v1/content/${id}/submit-review`, method: 'POST', data: { comment } }),
  approve: (id, comment = '') =>
    request({ url: `/api/v1/content/${id}/approve`, method: 'POST', data: { comment } }),
  reject: (id, comment = '') =>
    request({ url: `/api/v1/content/${id}/reject`, method: 'POST', data: { comment } }),
}
