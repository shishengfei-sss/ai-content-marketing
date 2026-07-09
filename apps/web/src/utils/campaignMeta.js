export const CAMPAIGN_STATUS_OPTIONS = [
  { value: 'draft', label: '草稿', tagType: 'info' },
  { value: 'active', label: '进行中', tagType: 'success' },
  { value: 'ended', label: '已结束', tagType: '' },
]

export const CAMPAIGN_CHANNEL_OPTIONS = [
  { value: 'wechat', label: '公众号' },
  { value: 'xhs', label: '小红书' },
  { value: 'douyin', label: '抖音' },
  { value: 'offline', label: '线下' },
  { value: 'other', label: '其他' },
]

const statusMap = Object.fromEntries(CAMPAIGN_STATUS_OPTIONS.map((s) => [s.value, s]))
const channelMap = Object.fromEntries(CAMPAIGN_CHANNEL_OPTIONS.map((c) => [c.value, c.label]))

export function campaignStatusLabel(status) {
  return statusMap[status]?.label || status
}

export function campaignStatusTagType(status) {
  return statusMap[status]?.tagType || 'info'
}

export function formatCampaignChannels(channels) {
  if (!channels?.length) return '—'
  return channels.map((c) => channelMap[c] || c).join('、')
}

export function formatCampaignPeriod(row) {
  if (!row?.start_at && !row?.end_at) return '—'
  const fmt = (value) => (value ? new Date(value).toLocaleDateString('zh-CN') : '…')
  return `${fmt(row.start_at)} ~ ${fmt(row.end_at)}`
}

export function toCampaignDateValue(value) {
  if (!value) return null
  return new Date(value).toISOString().slice(0, 10)
}

export function campaignDateToIso(value) {
  if (!value) return null
  return new Date(`${value}T00:00:00`).toISOString()
}
