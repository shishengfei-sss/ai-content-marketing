export const LEAD_STATUS_OPTIONS = ['待跟进', '跟进中', '有意向', '无意向', '已转化', '无效']

export const DEAL_STATUS_LABEL = {
  open: '进行中',
  won: '赢单',
  lost: '输单',
  abandoned: '放弃',
}

export const ORDER_STATUS_LABEL = {
  draft: '草稿',
  confirmed: '已确认',
  executing: '执行中',
  completed: '已完成',
  cancelled: '已取消',
}

export const QUOTE_STATUS_LABEL = {
  draft: '草稿',
  sent: '已发送',
  accepted: '已接受',
  rejected: '已拒绝',
  expired: '已过期',
}

export const CONTRACT_STATUS_LABEL = {
  draft: '草稿',
  sent: '已发送',
  signed: '已签署',
  executing: '执行中',
  expired: '已过期',
  terminated: '已终止',
}

export const PAYMENT_STATUS_LABEL = {
  pending: '待确认',
  confirmed: '已到账',
  reversed: '已冲销',
}

export function formatMoney(amount) {
  const n = Number(amount)
  if (!Number.isFinite(n)) return '—'
  return `¥${n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`
}
