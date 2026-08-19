import { computed, ref } from 'vue'

function defaultVisibleKeys(allColumns) {
  return allColumns
    .filter((c) => c.defaultOn ?? c.defaultVisible ?? false)
    .map((c) => c.key)
}

function loadVisibleKeys(allColumns, storageKey) {
  const defaults = defaultVisibleKeys(allColumns)
  const allKeys = new Set(allColumns.map((c) => c.key))
  try {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return defaults
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed) && parsed.length) {
      const valid = parsed.filter((key) => allKeys.has(key))
      const known = new Set(valid)
      for (const col of allColumns) {
        const onByDefault = col.defaultOn ?? col.defaultVisible ?? false
        if ((col.locked || onByDefault) && !known.has(col.key)) valid.push(col.key)
      }
      return valid
    }
    if (parsed && typeof parsed === 'object') {
      const visible = allColumns
        .filter((c) => parsed[c.key] || c.locked)
        .map((c) => c.key)
      const hidden = allColumns.map((c) => c.key).filter((k) => !visible.includes(k))
      return [...visible, ...hidden].filter((k) => allKeys.has(k))
    }
  } catch {
    /* ignore */
  }
  return defaults
}

/**
 * 列表列设置：显隐 + 顺序，持久化到 localStorage。
 * @param {Array<{key:string,label:string,locked?:boolean,defaultOn?:boolean,defaultVisible?:boolean}>} allColumns
 * @param {string} storageKey
 */
export function useListColumnSettings(allColumns, storageKey) {
  const columnDialogVisible = ref(false)
  const columnDraft = ref([])
  const visibleKeys = ref(loadVisibleKeys(allColumns, storageKey))

  const orderedVisibleColumns = computed(() =>
    visibleKeys.value
      .map((key) => allColumns.find((c) => c.key === key))
      .filter(Boolean),
  )

  function isColVisible(key) {
    return visibleKeys.value.includes(key)
  }

  function buildColumnDraft() {
    const hidden = allColumns.map((c) => c.key).filter((k) => !visibleKeys.value.includes(k))
    const orderedKeys = [...visibleKeys.value, ...hidden]
    return orderedKeys.map((key) => {
      const col = allColumns.find((c) => c.key === key)
      return {
        field_key: key,
        label: col.label,
        visible: visibleKeys.value.includes(key),
        list_locked: !!col.locked,
      }
    })
  }

  function openColumnSettings() {
    columnDraft.value = buildColumnDraft()
    columnDialogVisible.value = true
  }

  function saveColumnSettings() {
    visibleKeys.value = columnDraft.value
      .filter((c) => c.visible || c.list_locked)
      .map((c) => c.field_key)
    localStorage.setItem(storageKey, JSON.stringify(visibleKeys.value))
    columnDialogVisible.value = false
  }

  /** 兼容旧模板 colVisible[key] 写法（不含顺序） */
  function colVisibleMap() {
    return Object.fromEntries(allColumns.map((c) => [c.key, isColVisible(c.key)]))
  }

  return {
    visibleKeys,
    orderedVisibleColumns,
    columnDialogVisible,
    columnDraft,
    openColumnSettings,
    saveColumnSettings,
    isColVisible,
    colOn: isColVisible,
    colVisibleMap,
    buildColumnDraft,
  }
}
