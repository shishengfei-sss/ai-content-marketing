/** CRM 高级筛选（H5） */
export const FILTER_SKIP_FIELDS = new Set([
  'created_by_user_id',
  'updated_at',
  'last_follow_up_content',
  'converted_customer_id',
  'converted_from_lead_id',
  'credit_code',
  'campaign_id',
])

const TEXT_OPS = [
  { value: 'contains', label: '包含' },
  { value: 'eq', label: '等于' },
  { value: 'neq', label: '不等于' },
  { value: 'is_empty', label: '为空' },
]

const SELECT_OPS = [
  { value: 'eq', label: '等于' },
  { value: 'neq', label: '不等于' },
  { value: 'in', label: '属于' },
]

const NUMBER_OPS = [
  { value: 'eq', label: '等于' },
  { value: 'gt', label: '大于' },
  { value: 'gte', label: '大于等于' },
  { value: 'lt', label: '小于' },
  { value: 'lte', label: '小于等于' },
]

const DATE_OPS = [
  { value: 'eq', label: '等于' },
  { value: 'gte', label: '晚于' },
  { value: 'lte', label: '早于' },
]

const USER_OPS = [{ value: 'eq', label: '等于' }]

const OPS_BY_TYPE = {
  text: TEXT_OPS,
  phone: TEXT_OPS,
  email: TEXT_OPS,
  url: TEXT_OPS,
  textarea: TEXT_OPS,
  select: SELECT_OPS,
  number: NUMBER_OPS,
  currency: NUMBER_OPS,
  datetime: DATE_OPS,
  date: DATE_OPS,
  user_ref: USER_OPS,
  territory_ref: USER_OPS,
  ref: USER_OPS,
  checkbox: [{ value: 'eq', label: '等于' }],
}

export function normalizeFieldType(fieldType) {
  if (fieldType === 'currency') return 'number'
  if (fieldType === 'textarea' || fieldType === 'url') return 'text'
  if (fieldType === 'date') return 'datetime'
  return fieldType || 'text'
}

export function opsForFieldType(fieldType) {
  return OPS_BY_TYPE[fieldType] || TEXT_OPS
}

export function getFilterableFields(schemaFields) {
  return (schemaFields || [])
    .filter((f) => f.is_active !== false && !FILTER_SKIP_FIELDS.has(f.field_key))
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
}

export function createEmptyCondition() {
  return { field_key: '', op: 'contains', value: '' }
}

export function isConditionComplete(cond) {
  if (!cond?.field_key || !cond.op) return false
  if (cond.op === 'is_empty') return true
  const val = cond.value
  if (Array.isArray(val)) return val.length > 0
  return val !== '' && val !== null && val !== undefined
}

export function buildFiltersPayload(conditions, fields) {
  const fieldMap = Object.fromEntries((fields || []).map((f) => [f.field_key, f]))
  const valid = (conditions || []).filter(isConditionComplete).map((c) => {
    const row = { field_key: c.field_key, op: c.op }
    if (c.op === 'is_empty') return row
    const ft = fieldMap[c.field_key]?.field_type
    if (c.op === 'in' && !Array.isArray(c.value)) {
      row.value = c.value ? [c.value] : []
    } else if (normalizeFieldType(ft) === 'number' && c.value !== '') {
      row.value = Number(c.value)
    } else {
      row.value = c.value
    }
    return row
  })
  return { logic: 'and', conditions: valid }
}

export function countActiveFilters(filters) {
  return (filters?.conditions || []).filter(isConditionComplete).length
}

export function hasActiveFilters(filters) {
  return countActiveFilters(filters) > 0
}

export function filtersPayloadForApi(filters, fields) {
  const payload = buildFiltersPayload(filters?.conditions || [], fields)
  if (!payload.conditions.length) return undefined
  return JSON.stringify(payload)
}

export function summarizeFilters(filters, fieldMap) {
  const labels = []
  for (const cond of filters?.conditions || []) {
    if (!isConditionComplete(cond)) continue
    const field = fieldMap?.[cond.field_key]
    const label = field?.label || cond.field_key
    const opLabel = opsForFieldType(field?.field_type).find((o) => o.value === cond.op)?.label || cond.op
    if (cond.op === 'is_empty') {
      labels.push(`${label} ${opLabel}`)
    } else {
      const val = Array.isArray(cond.value) ? cond.value.join('、') : cond.value
      labels.push(`${label} ${opLabel} ${val}`)
    }
  }
  return labels
}

export function emptyFilters() {
  return { logic: 'and', conditions: [] }
}

export function draftFromFilters(filters) {
  const conds = filters?.conditions?.filter(isConditionComplete)
  if (conds?.length) return conds.map((c) => ({ ...c }))
  return [createEmptyCondition()]
}

export function suggestViewNameFromFilters(filters, fieldMap) {
  const parts = summarizeFilters(filters, fieldMap)
  if (!parts.length) return '我的视图'
  return parts.slice(0, 2).join('-').slice(0, 40)
}
