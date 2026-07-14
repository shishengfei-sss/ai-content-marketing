/** 线索/客户列表可排序的数据库字段 */
export const LEAD_SORTABLE_KEYS = new Set([
  'company_name',
  'contact_name',
  'mobile',
  'phone',
  'email',
  'source',
  'status',
  'created_at',
  'updated_at',
  'next_follow_up_at',
])

export const DEAL_SORTABLE_KEYS = new Set([
  'title',
  'amount',
  'status',
  'probability',
  'expected_close_date',
  'created_at',
  'updated_at',
  'closed_at',
])

export function isLeadColumnSortable(col) {
  return col && LEAD_SORTABLE_KEYS.has(col.field_key)
}

export function isDealColumnSortable(col) {
  return col && DEAL_SORTABLE_KEYS.has(col.field_key)
}
