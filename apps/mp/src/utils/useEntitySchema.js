import { ref } from 'vue'
import { crmApi } from '@/utils/api'
import { resolveMemberNameSync } from '@/utils/useTeamMembers'

const schemaCache = new Map()

export function useEntitySchema(entityType) {
  const fields = ref([])
  const listColumns = ref([])
  const loading = ref(false)

  function applyListColumns(columns) {
    listColumns.value = (columns || [])
      .map((c) => ({
        ...c,
        visible: c.list_locked ? true : c.visible !== false,
      }))
      .filter((c) => c.visible !== false)
      .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
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

  async function loadSchema() {
    const key = `schema:${entityType}`
    if (!schemaCache.has(key)) {
      const data = await crmApi.getSchema(entityType)
      schemaCache.set(key, data.fields || [])
    }
    fields.value = schemaCache.get(key)
    return fields.value
  }

  async function loadListColumns() {
    loading.value = true
    try {
      const data = await crmApi.getViewPreferences(entityType)
      let columns = data.columns || []
      const schemaFields = await loadSchema()
      const fieldMap = new Map((schemaFields || []).map((f) => [f.field_key, f]))
      if (!columns.length) {
        columns = buildDraftFromSchema(schemaFields.filter((f) => f.is_active !== false))
      }
      applyListColumns(
        columns.map((c) => ({
          ...c,
          field_type: c.field_type || fieldMap.get(c.field_key)?.field_type,
        })),
      )
    } catch {
      listColumns.value = []
    } finally {
      loading.value = false
    }
  }

  async function loadColumnSettingsDraft() {
    loading.value = true
    try {
      const [pref, schemaFields] = await Promise.all([
        crmApi.getViewPreferences(entityType),
        loadSchema(),
      ])
      const activeFields = (schemaFields || []).filter((f) => f.is_active !== false)
      const prefColumns = pref.columns || []
      if (!prefColumns.length) {
        return buildDraftFromSchema(activeFields)
      }
      return mergeColumnsWithSchema(prefColumns, activeFields)
    } finally {
      loading.value = false
    }
  }

  async function saveListColumns(columns) {
    await crmApi.saveViewPreferences(entityType, { columns })
    applyListColumns(columns)
  }

  function formatCell(row, fieldKey, fieldType) {
    const resolveRef = (val, type) => {
      if (val === undefined || val === null || val === '') return '—'
      if (type === 'user_ref' || fieldKey === 'owner_user_id' || fieldKey === 'created_by_user_id') {
        const name = resolveMemberNameSync(val, { empty: '' })
        return name || '—'
      }
      return null
    }

    const formatValue = (val, type) => {
      const refLabel = resolveRef(val, type || fieldType)
      if (refLabel !== null) return refLabel
      if (type === 'datetime' || type === 'date' || fieldType === 'datetime' || fieldType === 'date') {
        return new Date(val).toLocaleString('zh-CN')
      }
      if (Array.isArray(val)) return val.join('、')
      return String(val)
    }

    if (row[fieldKey] !== undefined && row[fieldKey] !== null && row[fieldKey] !== '') {
      return formatValue(row[fieldKey], fieldType)
    }
    const extra = row.extra_data || {}
    const val = extra[fieldKey]
    if (val === undefined || val === null || val === '') return '—'
    return formatValue(val, fieldType)
  }

  return {
    fields,
    listColumns,
    loading,
    loadSchema,
    loadListColumns,
    loadColumnSettingsDraft,
    saveListColumns,
    applyListColumns,
    formatCell,
  }
}
