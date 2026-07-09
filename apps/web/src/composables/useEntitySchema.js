import { ref } from 'vue'
import { crmApi } from '../api/client'

const schemaCache = new Map()

export function useEntitySchema(entityType) {
  const fields = ref([])
  const listColumns = ref([])
  const allListColumns = ref([])
  const loading = ref(false)

  async function loadSchema() {
    loading.value = true
    try {
      const key = `schema:${entityType}`
      if (!schemaCache.has(key)) {
        const { data } = await crmApi.getSchema(entityType)
        schemaCache.set(key, data.fields || [])
      }
      fields.value = schemaCache.get(key)
    } finally {
      loading.value = false
    }
  }

  function enrichListColumns(columns, schemaFields) {
    const fieldMap = new Map((schemaFields || []).map((f) => [f.field_key, f]))
    let cols = (columns || []).map((c) => ({
      ...c,
      field_type: c.field_type || fieldMap.get(c.field_key)?.field_type,
    }))
    if (entityType === 'lead' && !cols.some((c) => c.field_key === 'created_at' && c.visible !== false)) {
      const f = fieldMap.get('created_at')
      if (f) {
        const existing = cols.find((c) => c.field_key === 'created_at')
        if (existing) {
          existing.visible = true
          existing.field_type = existing.field_type || f.field_type
        } else {
          cols = [
            ...cols,
            {
              field_key: 'created_at',
              label: f.label,
              field_type: f.field_type,
              visible: true,
              order: f.sort_order ?? 910,
            },
          ]
        }
      }
    }
    return cols.sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
  }

  function applyListColumns(columns, schemaFields = null) {
    const fields = schemaFields || schemaCache.get(`schema:${entityType}`) || []
    const enriched = enrichListColumns(columns, fields)
    allListColumns.value = enriched.map((c) => ({
      ...c,
      visible: c.list_locked ? true : c.visible !== false,
    }))
    listColumns.value = allListColumns.value.filter((c) => c.visible !== false)
  }

  function buildDraftFromSchema(schemaFields) {
    return [...schemaFields]
      .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
      .map((f, i) => ({
        field_key: f.field_key,
        label: f.label,
        list_locked: !!f.list_locked,
        visible: f.list_locked ? true : !!f.show_in_list_default,
        order: i,
      }))
  }

  function mergeColumnsWithSchema(prefColumns, schemaFields) {
    const fieldMap = new Map(schemaFields.map((f) => [f.field_key, f]))
    const draft = []
    const used = new Set()

    for (const col of prefColumns || []) {
      const f = fieldMap.get(col.field_key)
      if (!f) continue
      draft.push({
        field_key: f.field_key,
        label: f.label,
        list_locked: !!f.list_locked,
        visible: f.list_locked ? true : col.visible !== false,
        order: col.order ?? draft.length,
      })
      used.add(f.field_key)
    }

    for (const f of schemaFields) {
      if (used.has(f.field_key)) continue
      draft.push({
        field_key: f.field_key,
        label: f.label,
        list_locked: !!f.list_locked,
        visible: !!f.list_locked,
        order: draft.length,
      })
    }

    return draft.sort((a, b) => a.order - b.order)
  }

  async function loadListColumns() {
    loading.value = true
    try {
      const { data } = await crmApi.getViewPreferences(entityType)
      let columns = data.columns || []
      if (!columns.length) {
        await loadSchema()
        columns = buildDraftFromSchema(fields.value).map((c) => ({
          ...c,
          field_type: fields.value.find((f) => f.field_key === c.field_key)?.field_type,
        }))
      } else {
        await loadSchema()
        columns = enrichListColumns(columns, fields.value)
      }
      applyListColumns(columns, fields.value)
    } finally {
      loading.value = false
    }
  }

  /** 列设置弹窗：含隐藏列；必要时合并 schema 全量字段 */
  async function loadColumnSettingsDraft() {
    loading.value = true
    try {
      const [{ data: pref }, schemaResult] = await Promise.all([
        crmApi.getViewPreferences(entityType),
        schemaCache.has(`schema:${entityType}`)
          ? Promise.resolve({ data: { fields: schemaCache.get(`schema:${entityType}`) } })
          : crmApi.getSchema(entityType),
      ])
      const schemaFields = (schemaResult.data.fields || []).filter((f) => f.is_active !== false)
      schemaCache.set(`schema:${entityType}`, schemaResult.data.fields || [])
      fields.value = schemaCache.get(`schema:${entityType}`)

      const prefColumns = pref.columns || []
      if (!prefColumns.length) {
        return buildDraftFromSchema(schemaFields)
      }
      return mergeColumnsWithSchema(prefColumns, schemaFields)
    } finally {
      loading.value = false
    }
  }

  async function saveListColumns(columns) {
    await crmApi.saveViewPreferences(entityType, { columns })
    applyListColumns(columns, fields.value)
  }

  function formatCell(row, fieldKey, fieldType) {
    const formatValue = (val) => {
      if (fieldType === 'datetime' || fieldType === 'date') {
        return new Date(val).toLocaleString('zh-CN')
      }
      if (Array.isArray(val)) return val.join('、')
      return String(val)
    }
    if (row[fieldKey] !== undefined && row[fieldKey] !== null && row[fieldKey] !== '') {
      if (fieldType === 'datetime' || fieldType === 'date') {
        return formatValue(row[fieldKey])
      }
      return row[fieldKey]
    }
    const extra = row.extra_data || {}
    const val = extra[fieldKey]
    if (val === undefined || val === null || val === '') return '—'
    return formatValue(val)
  }

  return {
    fields,
    listColumns,
    allListColumns,
    loading,
    loadSchema,
    loadListColumns,
    loadColumnSettingsDraft,
    saveListColumns,
    formatCell,
    applyListColumns,
  }
}
