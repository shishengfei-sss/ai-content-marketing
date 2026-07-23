/** 静态兜底（字典未加载或离线时）；正式选项以 API campaign-channels 为准 */
import { formatDate } from './datetime'

export const CAMPAIGN_CHANNEL_OPTIONS = [
  { value: 'wechat', label: '公众号' },
  { value: 'xhs', label: '小红书' },
  { value: 'douyin', label: '抖音' },
  { value: 'offline', label: '线下' },
  { value: 'other', label: '其他' },
]

export const CAMPAIGN_STATUS_OPTIONS = [
  { value: 'draft', label: '草稿', tagType: 'info' },
  { value: 'active', label: '进行中', tagType: 'success' },
  { value: 'paused', label: '已暂停', tagType: 'warning' },
  { value: 'ended', label: '已结束', tagType: '' },
]

export const CAMPAIGN_TYPE_OPTIONS = [
  { value: 'content', label: '内容投放' },
  { value: 'online', label: '线上推广' },
  { value: 'offline', label: '线下活动' },
  { value: 'exhibition', label: '展会' },
  { value: 'training', label: '培训' },
  { value: 'other', label: '其他' },
]

export const CAMPAIGN_CURRENCY_OPTIONS = [{ value: 'CNY', label: 'CNY' }]

export const CHANNEL_CONTENT_TYPE_OPTIONS = [
  { value: 'post', label: '帖子' },
  { value: 'ad', label: '广告' },
  { value: 'article', label: '文章' },
  { value: 'email', label: '邮件' },
  { value: 'video', label: '短视频' },
  { value: 'live', label: '直播' },
]

export const CHANNEL_EXECUTION_STATUS_OPTIONS = [
  { value: 'planned', label: '计划中' },
  { value: 'published', label: '已发布' },
  { value: 'paused', label: '已暂停' },
]

const LOCATION_TYPES = new Set(['offline', 'exhibition', 'training'])

const statusMap = Object.fromEntries(CAMPAIGN_STATUS_OPTIONS.map((s) => [s.value, s]))
const typeMap = Object.fromEntries(CAMPAIGN_TYPE_OPTIONS.map((t) => [t.value, t.label]))
const contentTypeMap = Object.fromEntries(CHANNEL_CONTENT_TYPE_OPTIONS.map((t) => [t.value, t.label]))
const execStatusMap = Object.fromEntries(CHANNEL_EXECUTION_STATUS_OPTIONS.map((s) => [s.value, s.label]))

export function campaignStatusLabel(status) {
  return statusMap[status]?.label || status
}

export function campaignStatusTagType(status) {
  return statusMap[status]?.tagType || 'info'
}

export function campaignTypeLabel(type) {
  if (!type) return '—'
  return typeMap[type] || type
}

export function channelContentTypeLabel(type) {
  if (!type) return '—'
  return contentTypeMap[type] || type
}

export function channelExecutionStatusLabel(status) {
  if (!status) return '—'
  return execStatusMap[status] || status
}

export function showCampaignLocation(type) {
  return LOCATION_TYPES.has(type)
}

export function channelsToOptions(rows) {
  if (!rows?.length) return [...CAMPAIGN_CHANNEL_OPTIONS]
  return rows.map((r) => ({ value: r.code, label: r.name }))
}

export function buildChannelLabelMap(rows) {
  const map = Object.fromEntries(CAMPAIGN_CHANNEL_OPTIONS.map((c) => [c.value, c.label]))
  for (const row of rows || []) {
    if (row?.code) map[row.code] = row.name || row.code
  }
  return map
}

export function formatCampaignChannels(channels, labelMap) {
  if (!channels?.length) return '—'
  const map = labelMap || Object.fromEntries(CAMPAIGN_CHANNEL_OPTIONS.map((c) => [c.value, c.label]))
  return channels.map((c) => map[c] || c).join('、')
}

export function formatCampaignPeriod(row) {
  if (!row?.start_at && !row?.end_at) return '—'
  const fmt = (value) => (value ? formatDate(value, { empty: '…' }) : '…')
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
