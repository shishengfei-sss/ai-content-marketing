export const FORM_SKIP_FIELD_KEYS = new Set([
  'created_by_user_id',
  'created_at',
  'updated_at',
  'owner_user_id',
  'last_follow_up_at',
  'last_follow_up_content',
  'converted_customer_id',
  'next_follow_up_at',
  'converted_from_lead_id',
])

export const ENTITY_DB_FIELDS = {
  lead: new Set([
    'company_name',
    'contact_name',
    'mobile',
    'phone',
    'email',
    'source',
    'status',
    'remark',
    'campaign_id',
    'territory_id',
  ]),
  customer: new Set(['company_name', 'mobile', 'phone', 'email', 'status', 'remark']),
}

const SECTION_RULES = [
  { id: 'basic', label: '基本信息', maxOrder: 45 },
  { id: 'contact', label: '联系方式', maxOrder: 89 },
  { id: 'address', label: '地址信息', maxOrder: 129 },
  { id: 'business', label: '业务信息', maxOrder: 219 },
  { id: 'sales', label: '销售跟进', maxOrder: 279 },
  { id: 'other', label: '其他', maxOrder: Infinity },
]

export const REGION_FIELD_KEYS = new Set(['province', 'city', 'district'])

export const LEAD_STATUS_OPTIONS = ['待跟进', '跟进中', '有意向', '无意向', '已转化', '无效']
export const CUSTOMER_STATUS_OPTIONS = ['潜在', '意向', '成交', '在服', '暂停', '流失']

/** 线索表单字段布局（覆盖存量租户 schema 排序/标签） */
const LEAD_FIELD_OVERRIDES = {
  company_name: { sort_order: 10, label: '公司名称' },
  credit_code: { sort_order: 20, label: '统一社会信用代码' },
  contact_name: { sort_order: 48, label: '联系人姓名' },
  mobile: { sort_order: 50, label: '手机' },
  phone: { sort_order: 60, label: '电话' },
  wechat: { sort_order: 70, label: '微信' },
  qq: { sort_order: 75, label: 'QQ' },
  email: { sort_order: 80, label: '邮箱' },
  website: { sort_order: 85, label: '网址' },
  province: { sort_order: 90, label: '省' },
  city: { sort_order: 100, label: '市' },
  district: { sort_order: 110, label: '区/县' },
  address: { sort_order: 120, label: '详细地址' },
  industry: { sort_order: 130 },
  company_scale: { sort_order: 140 },
  annual_revenue: { sort_order: 150, label: '年营业额' },
  taxpayer_type: { sort_order: 160 },
  main_business: { sort_order: 170 },
  accounting_need: { sort_order: 180 },
  source: { sort_order: 200 },
  source_detail: { sort_order: 210 },
  status: { sort_order: 220 },
  intention_level: { sort_order: 230 },
  campaign_id: { sort_order: 240 },
  next_follow_up_at: { sort_order: 250 },
  last_follow_up_at: { sort_order: 260 },
  last_follow_up_content: { sort_order: 270 },
  remark: { sort_order: 280 },
}

/** 客户表单字段布局：级别/状态归入基本信息，联系方式单独分区 */
const CUSTOMER_FIELD_OVERRIDES = {
  company_name: { sort_order: 10, label: '客户名称' },
  short_name: { sort_order: 20, label: '客户简称' },
  customer_level: { sort_order: 30, label: '客户级别' },
  status: { sort_order: 40, label: '客户状态' },
  mobile: { sort_order: 50, label: '主手机' },
  phone: { sort_order: 60, label: '主电话' },
  email: { sort_order: 70, label: '邮箱' },
  wechat: { sort_order: 80, label: '微信' },
  province: { sort_order: 90 },
  city: { sort_order: 100 },
  district: { sort_order: 110 },
  address: { sort_order: 120, label: '详细地址' },
  industry: { sort_order: 130 },
  company_scale: { sort_order: 140 },
  credit_code: { sort_order: 150 },
  taxpayer_type: { sort_order: 160 },
  legal_representative: { sort_order: 170 },
  registered_capital: { sort_order: 180 },
  service_type: { sort_order: 190 },
  service_start_at: { sort_order: 200 },
  contract_amount: { sort_order: 210 },
  remark: { sort_order: 260, label: '备注' },
}

export const ENTITY_FORM_SKIP = {
  // 新建客户时联系方式改由「联系人」区块维护，避免与多联系人重复
  customer: new Set(['campaign_id', 'territory_id', 'converted_from_lead_id']),
  customer_create: new Set([
    'campaign_id',
    'territory_id',
    'converted_from_lead_id',
    'mobile',
    'phone',
    'email',
    'wechat',
  ]),
  lead: new Set(),
}

export function emptyContactDraft(isPrimary = false) {
  return {
    name: '',
    mobile: '',
    phone: '',
    email: '',
    wechat: '',
    title: '',
    department: '',
    is_primary: isPrimary,
    is_decision_maker: false,
  }
}

/** 业务层必填（含存量租户 schema 未同步 is_required 的字段） */
const ENTITY_REQUIRED_KEYS = {
  lead: new Set(['company_name', 'contact_name', 'mobile', 'status']),
  customer: new Set(['company_name']),
}

export function isFormFieldRequired(entityType, field) {
  if (!field) return false
  if (field.is_required) return true
  const keys = ENTITY_REQUIRED_KEYS[entityType]
  return keys ? keys.has(field.field_key) : false
}

function fieldOverridesFor(entityType) {
  if (entityType === 'lead') return LEAD_FIELD_OVERRIDES
  if (entityType === 'customer' || entityType === 'customer_create') return CUSTOMER_FIELD_OVERRIDES
  return null
}

export function getFormFields(schemaFields, entityType = '') {
  const baseType = entityType === 'customer_create' ? 'customer' : entityType
  const extraSkip = ENTITY_FORM_SKIP[entityType] || ENTITY_FORM_SKIP[baseType] || new Set()
  const overridesMap = fieldOverridesFor(entityType)
  return (schemaFields || [])
    .filter(
      (f) =>
        f.is_active !== false &&
        !FORM_SKIP_FIELD_KEYS.has(f.field_key) &&
        !extraSkip.has(f.field_key),
    )
    .map((f) => {
      const overrides = overridesMap?.[f.field_key]
      const merged = overrides ? { ...f, ...overrides } : { ...f }
      return {
        ...merged,
        is_required: isFormFieldRequired(baseType, merged),
      }
    })
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
}

export function fieldsWithoutRegionParts(fields) {
  return (fields || []).filter((f) => !REGION_FIELD_KEYS.has(f.field_key))
}

export function hasRegionFields(fields) {
  return (fields || []).some((f) => REGION_FIELD_KEYS.has(f.field_key))
}

function fieldSectionId(field) {
  const order = field.sort_order ?? 0
  return SECTION_RULES.find((rule) => order <= rule.maxOrder)?.id || 'other'
}

export function groupFormFields(fields) {
  const groups = []
  const map = new Map()

  for (const field of fields) {
    const sectionId = fieldSectionId(field)
    if (!map.has(sectionId)) {
      const meta = SECTION_RULES.find((rule) => rule.id === sectionId) || SECTION_RULES.at(-1)
      const group = { id: sectionId, title: meta.label, fields: [] }
      map.set(sectionId, group)
      groups.push(group)
    }
    map.get(sectionId).fields.push(field)
  }

  return groups
}

function defaultFieldValue(field) {
  if (field.field_type === 'multiselect') return []
  if (field.field_type === 'checkbox') return false
  return field.default_value ?? ''
}

export function entityToFormValues(record, fields) {
  const values = {}
  for (const field of fields) {
    const key = field.field_key
    const top = record?.[key]
    const extra = record?.extra_data?.[key]
    if (top !== undefined && top !== null && top !== '') {
      values[key] = top
    } else if (extra !== undefined && extra !== null && extra !== '') {
      values[key] = extra
    } else {
      values[key] = defaultFieldValue(field)
    }
  }
  return values
}

function normalizeValue(field, raw) {
  if (raw === '' || raw === undefined) return null
  if (Array.isArray(raw) && raw.length === 0) return null
  if (field.field_type === 'datetime' && raw) {
    return new Date(raw).toISOString()
  }
  if (field.field_type === 'date' && raw) {
    return new Date(`${raw}T00:00:00`).toISOString()
  }
  return raw
}

export const LEAD_MOBILE_RE = /^1[3-9]\d{9}$/

export function validateLeadMobile(mobile, { required = true } = {}) {
  const value = String(mobile ?? '').trim()
  if (!value) {
    return required ? '请填写手机号' : null
  }
  if (!LEAD_MOBILE_RE.test(value)) {
    return '手机号格式无效，须为 11 位中国大陆手机号'
  }
  return null
}

export function formValuesToPayload(entityType, values, fields) {
  const baseType = entityType === 'customer_create' ? 'customer' : entityType
  const dbKeys = ENTITY_DB_FIELDS[baseType] || new Set()
  const payload = { extra_data: {} }

  for (const field of fields) {
    const key = field.field_key
    const val = normalizeValue(field, values[key])
    if (dbKeys.has(key)) {
      payload[key] = val
    } else if (val !== null) {
      payload.extra_data[key] = val
    }
  }

  return payload
}

export function formatFieldDisplay(field, record) {
  const key = field.field_key
  let val = record?.[key]
  if (val === undefined || val === null || val === '') {
    val = record?.extra_data?.[key]
  }
  if (val === undefined || val === null || val === '') return '—'
  if (field.field_type === 'datetime' || field.field_type === 'date') {
    return new Date(val).toLocaleString('zh-CN')
  }
  if (Array.isArray(val)) return val.join('、')
  if (field.field_type === 'checkbox') return val ? '是' : '否'
  return String(val)
}
