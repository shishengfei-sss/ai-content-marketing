import { computed } from 'vue'

const LEFT_FIXED_KEYS = new Set(['company_name'])
const RIGHT_FIXED_KEYS = new Set(['owner_user_id'])

/** 将动态列拆为左冻结 / 滚动 / 右冻结，供 el-table 使用。 */
export function useCrmListColumns(listColumns) {
  const leftFixedColumns = computed(() =>
    listColumns.value.filter((c) => LEFT_FIXED_KEYS.has(c.field_key)),
  )
  const scrollColumns = computed(() =>
    listColumns.value.filter(
      (c) => !LEFT_FIXED_KEYS.has(c.field_key) && !RIGHT_FIXED_KEYS.has(c.field_key),
    ),
  )
  const rightFixedColumns = computed(() =>
    listColumns.value.filter((c) => RIGHT_FIXED_KEYS.has(c.field_key)),
  )
  return { leftFixedColumns, scrollColumns, rightFixedColumns }
}
