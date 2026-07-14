/** H5 列表卡片摘要：严格按列设置（可见 + 顺序）展示，标题/状态单独渲染 */

const CARD_HEAD_FIELDS_BY_ENTITY = {
  lead: ['company_name', 'status'],
  customer: ['company_name', 'status'],
  deal: ['title', 'status'],
  order: ['title', 'status'],
  quote: ['subject', 'status'],
  contract: ['title', 'status'],
  payment: ['payment_number', 'status'],
}

function cardHeadFields(entityType, extra = []) {
  const base = entityType
    ? CARD_HEAD_FIELDS_BY_ENTITY[entityType] || ['status']
    : ['company_name', 'status']
  return new Set([...base, ...extra])
}

function cardDisplayColumns(columns, headFields) {
  return [...(columns || [])]
    .filter((c) => c.visible !== false && !headFields.has(c.field_key))
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
}

export function buildCardMetaItems(row, columns, formatCell, { max = 0, entityType, headExtra = [] } = {}) {
  const head = cardHeadFields(entityType, headExtra)
  const ordered = cardDisplayColumns(columns, head)
  const items = []
  for (const col of ordered) {
    const val = formatCell(row, col.field_key, col.field_type)
    if (val === '—') continue
    items.push({ field_key: col.field_key, label: col.label, value: val })
    if (max > 0 && items.length >= max) break
  }
  return items
}

export function buildCardMetaLine(row, columns, formatCell, { max = 0, withLabel = true, entityType, headExtra = [] } = {}) {
  const items = buildCardMetaItems(row, columns, formatCell, { max, entityType, headExtra })
  if (!items.length) return '—'
  if (withLabel) {
    return items.map((i) => `${i.label}：${i.value}`).join(' · ')
  }
  return items.map((i) => i.value).join(' · ')
}
