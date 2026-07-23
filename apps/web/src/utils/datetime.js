/** CRM / 业务时间展示：统一按北京时间（Asia/Shanghai）。 */

export const APP_TIME_ZONE = 'Asia/Shanghai'

/**
 * 解析接口时间。无时区后缀的 ISO 视为 UTC（与后端 timestamptz / UTC 存储一致）。
 */
export function parseApiDateTime(value) {
  if (value == null || value === '') return null
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }
  const raw = String(value).trim()
  if (!raw) return null

  // 纯日期：按日历日展示，不当作 UTC 时刻
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    const d = new Date(`${raw}T12:00:00+08:00`)
    return Number.isNaN(d.getTime()) ? null : d
  }

  let s = raw.includes('T') ? raw : raw.replace(' ', 'T')
  // 已有 Z / ±HH:MM
  if (/([zZ]|[+-]\d{2}:?\d{2})$/.test(s)) {
    const d = new Date(s)
    return Number.isNaN(d.getTime()) ? null : d
  }
  // 微秒裁到毫秒，再按 UTC 解析
  s = s.replace(/(\.\d{3})\d+/, '$1')
  const d = new Date(`${s}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatDateTime(value, { empty = '—', withSeconds = true } = {}) {
  const d = parseApiDateTime(value)
  if (!d) return empty
  const opts = {
    timeZone: APP_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }
  if (withSeconds) opts.second = '2-digit'
  return d.toLocaleString('zh-CN', opts)
}

export function formatDate(value, { empty = '—' } = {}) {
  if (value == null || value === '') return empty
  const raw = String(value).trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    const [y, m, day] = raw.split('-')
    return `${y}/${Number(m)}/${Number(day)}`
  }
  const d = parseApiDateTime(value)
  if (!d) return empty
  return d.toLocaleDateString('zh-CN', { timeZone: APP_TIME_ZONE })
}

/** 仅时分（北京时间），用于日历等拆分展示 */
export function formatTimeOfDay(value, { empty = '—' } = {}) {
  const d = parseApiDateTime(value)
  if (!d) return empty
  return d.toLocaleTimeString('zh-CN', {
    timeZone: APP_TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}
