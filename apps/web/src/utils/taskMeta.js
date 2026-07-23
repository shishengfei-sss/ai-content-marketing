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

/** 根据当前状态返回可执行的操作（取消与删除互斥：待办走删除，已开始走取消） */
export function getTaskStatusActions(status) {
  if (status === 'done' || status === 'cancelled') return []
  const actions = []
  if (status === 'open') {
    actions.push({ key: 'start', label: '开始', next: 'in_progress', primary: true })
    actions.push({ key: 'hold', label: '挂起', next: 'on_hold' })
    actions.push({ key: 'done', label: '完成', next: 'done', success: true })
    return actions
  }
  if (status === 'in_progress') {
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

/** 取消任务时弹出填写取消原因；取消对话框则抛出 'cancel' */
export async function promptTaskCancelReason() {
  const { ElMessageBox } = await import('element-plus')
  const { value } = await ElMessageBox.prompt('请填写取消原因（必填）', '取消任务', {
    confirmButtonText: '确认取消',
    cancelButtonText: '返回',
    type: 'warning',
    inputType: 'textarea',
    inputPlaceholder: '例如：客户延期、需求变更、重复任务…',
    inputValidator: (v) => {
      const text = String(v || '').trim()
      if (!text) return '请填写取消原因'
      if (text.length > 500) return '取消原因不超过 500 字'
      return true
    },
  })
  return String(value).trim()
}

/** 标记完成前二次确认，避免误点左侧勾选 */
export async function promptTaskCompleteConfirm(title = '') {
  const { ElMessageBox } = await import('element-plus')
  const name = String(title || '').trim()
  const tip = name ? `确定将任务「${name}」标记为已完成？` : '确定将此任务标记为已完成？'
  await ElMessageBox.confirm(tip, '完成任务', {
    confirmButtonText: '确认完成',
    cancelButtonText: '取消',
    type: 'warning',
  })
}

import { formatDateTime, parseApiDateTime } from './datetime'

export function formatTaskDateTime(value, { empty = '—' } = {}) {
  return formatDateTime(value, { empty, withSeconds: false })
}

export function formatDueAtRelative(value) {
  if (!value) return '无计划完成时间'
  const date = parseApiDateTime(value)
  if (!date) return '无计划完成时间'
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const diff = Math.round((target - today) / 86400000)
  const time = formatDateTime(value, { empty: '', withSeconds: false }).split(' ')[1] || ''
  const day = formatDateTime(value, { empty: '', withSeconds: false }).split(' ')[0] || ''
  if (diff < 0) return `已逾期 · ${day} ${time}`
  if (diff === 0) return `今天 ${time}`
  if (diff === 1) return `明天 ${time}`
  return `${day} ${time}`
}

export const TASK_TIME_FIELDS = [
  { key: 'planned_start_at', label: '计划开始' },
  { key: 'started_at', label: '实际开始' },
  { key: 'due_at', label: '计划完成' },
  { key: 'completed_at', label: '实际完成' },
]
