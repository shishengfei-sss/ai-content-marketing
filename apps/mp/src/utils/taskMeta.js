export const TASK_STATUS_LABELS = {
  open: '待办',
  in_progress: '进行中',
  on_hold: '已挂起',
  done: '已完成',
  cancelled: '已取消',
}

export const TASK_PRIORITY_LABELS = {
  low: '低',
  normal: '普通',
  high: '高',
}

import { formatDateTime, parseApiDateTime } from './datetime'

export function getTaskStatusActions(status) {
  if (status === 'done' || status === 'cancelled') return []
  const actions = []
  if (status === 'open') {
    actions.push({ key: 'start', label: '开始', next: 'in_progress', primary: true })
    actions.push({ key: 'hold', label: '挂起', next: 'on_hold' })
  } else if (status === 'in_progress') {
    actions.push({ key: 'hold', label: '挂起', next: 'on_hold' })
  } else if (status === 'on_hold') {
    actions.push({ key: 'resume', label: '继续', next: 'in_progress', primary: true })
  }
  actions.push({ key: 'done', label: '完成', next: 'done' })
  actions.push({ key: 'cancel', label: '取消', next: 'cancelled', muted: true })
  return actions
}

export const TASK_STATUS_CHANGE_MESSAGES = {
  in_progress: '任务已开始',
  on_hold: '任务已挂起',
  done: '任务已完成',
  cancelled: '任务已取消',
}

export function isActiveTaskStatus(status) {
  return status !== 'done' && status !== 'cancelled'
}

export function formatTaskDateTime(value, { empty = '—' } = {}) {
  return formatDateTime(value, { empty, withSeconds: false })
}

export function formatDueAtRelative(value) {
  if (!value) return '未设置'
  const date = parseApiDateTime(value)
  if (!date) return '未设置'
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const diff = Math.round((target - today) / 86400000)
  const time = formatDateTime(value, { empty: '', withSeconds: false }).split(' ')[1] || ''
  const day = formatDateTime(value, { empty: '', withSeconds: false }).split(' ')[0] || ''
  if (diff < 0) return `已逾期 ${day} ${time}`
  if (diff === 0) return `今天 ${time}`
  if (diff === 1) return `明天 ${time}`
  return `${day} ${time}`
}

export const TASK_TIME_FIELDS = [
  { key: 'planned_start_at', label: '计划开始' },
  { key: 'started_at', label: '实际开始', actual: true },
  { key: 'due_at', label: '计划完成' },
  { key: 'completed_at', label: '实际完成', actual: true },
]

export const PRIORITY_OPTIONS = [
  { value: 'low', label: '低' },
  { value: 'normal', label: '普通' },
  { value: 'high', label: '高' },
]

/** datetime-local 字符串 → ISO（兼容 iOS 对无秒/无时区的解析） */
export function datetimeLocalToIso(localStr) {
  if (!localStr || !String(localStr).trim()) return null
  let s = String(localStr).trim().replace(' ', 'T')
  // iOS：需要完整到秒，且无时区时按本地时间理解
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(s)) s = `${s}:00`
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return null
  return d.toISOString()
}

/** ISO → datetime-local 值 */
export function isoToDatetimeLocal(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
