export const TASK_STATUS_LABELS = {
  open: '待办',
  in_progress: '进行中',
  on_hold: '已挂起',
  done: '已完成',
  cancelled: '已取消',
}

export const TASK_STATUS_TYPES = {
  open: 'info',
  in_progress: 'primary',
  on_hold: 'warning',
  done: 'success',
  cancelled: 'info',
}

export const TASK_PRIORITY_LABELS = {
  low: '低',
  normal: '普通',
  high: '高',
}

export const TASK_PRIORITY_TYPES = {
  low: 'info',
  normal: '',
  high: 'danger',
}

/** 根据当前状态返回可执行的操作 */
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
  actions.push({ key: 'done', label: '完成', next: 'done', success: true })
  actions.push({ key: 'cancel', label: '取消', next: 'cancelled', muted: true })
  return actions
}

/** 列表操作列：主操作（开始/继续/完成） */
export function getPrimaryTaskAction(status) {
  const actions = getTaskStatusActions(status)
  return actions.find((a) => a.primary) || actions.find((a) => a.success) || actions[0] || null
}

/** 列表操作列：次要操作（放入「更多」） */
export function getSecondaryTaskActions(status) {
  const primary = getPrimaryTaskAction(status)
  return getTaskStatusActions(status).filter((a) => a.key !== primary?.key)
}

export const TASK_STATUS_CHANGE_MESSAGES = {
  in_progress: '任务已开始',
  on_hold: '任务已挂起',
  open: '任务已恢复',
  done: '任务已完成',
  cancelled: '任务已取消',
}

export function isActiveTaskStatus(status) {
  return status !== 'done' && status !== 'cancelled'
}

export function formatTaskDateTime(value, { empty = '—' } = {}) {
  if (!value) return empty
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return empty
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDueAtRelative(value) {
  if (!value) return '无计划完成时间'
  const date = new Date(value)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const diff = Math.round((target - today) / 86400000)
  const time = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (diff < 0) return `已逾期 · ${date.toLocaleDateString('zh-CN')} ${time}`
  if (diff === 0) return `今天 ${time}`
  if (diff === 1) return `明天 ${time}`
  return `${date.toLocaleDateString('zh-CN')} ${time}`
}

export const TASK_TIME_FIELDS = [
  { key: 'planned_start_at', label: '计划开始' },
  { key: 'started_at', label: '实际开始' },
  { key: 'due_at', label: '计划完成' },
  { key: 'completed_at', label: '实际完成' },
]
