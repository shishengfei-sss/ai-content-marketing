const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''



export { BASE_URL }



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

  login: (phone, password) =>

    request({ url: '/api/v1/auth/login', method: 'POST', data: { phone, password } }),

  sendSmsCode: (phone) =>

    request({ url: '/api/v1/auth/sms/send', method: 'POST', data: { phone } }),

  loginBySms: (phone, code) =>

    request({ url: '/api/v1/auth/sms/login', method: 'POST', data: { phone, code } }),

  register: (payload) =>

    request({ url: '/api/v1/auth/register', method: 'POST', data: payload }),

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


