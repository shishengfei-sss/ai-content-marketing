/** H5 工作台/销售页展示格式化 */

export function formatCompactMoney(amount) {
  const n = Number(amount)
  if (!Number.isFinite(n)) return '—'
  if (Math.abs(n) >= 10000) {
    const wan = n / 10000
    const text = wan >= 10 ? wan.toFixed(0) : wan.toFixed(1)
    return `${text.replace(/\.0$/, '')}万`
  }
  return `¥${n.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
}

export function formatRelativeTime(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 0) return '刚刚'
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}天前`
  return new Date(iso).toLocaleDateString('zh-CN')
}

export function monthEndLabel(date = new Date()) {
  const end = new Date(date.getFullYear(), date.getMonth() + 1, 0)
  return `截止 ${end.getMonth() + 1}月${end.getDate()}日`
}

export function daysLeftInMonth(date = new Date()) {
  const end = new Date(date.getFullYear(), date.getMonth() + 1, 0)
  return Math.max(0, end.getDate() - date.getDate())
}

export function isThisMonth(iso) {
  if (!iso) return false
  const d = new Date(iso)
  const now = new Date()
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()
}

export function calcProgress(current, target) {
  const c = Number(current) || 0
  const t = Number(target) || 0
  if (t <= 0) return 0
  return Math.min(100, Math.round((c / t) * 100))
}

export function deriveSalesTarget(weightedAmount, wonAmount) {
  const w = Number(weightedAmount) || 0
  const won = Number(wonAmount) || 0
  if (w > 0) return Math.ceil((w * 1.2) / 10000) * 10000
  if (won > 0) return Math.ceil((won * 1.5) / 10000) * 10000
  return 100000
}
