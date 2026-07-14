import { computed, ref, watch } from 'vue'
import { crmApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { useEntitySchema } from '@/utils/useEntitySchema'
import {
  buildFiltersPayload,
  countActiveFilters,
  createEmptyCondition,
  draftFromFilters,
  emptyFilters,
  filtersPayloadForApi,
  getFilterableFields,
  opsForFieldType,
  summarizeFilters,
} from '@/utils/crmAdvancedFilter'
import { useTeamMembers } from '@/utils/useTeamMembers'

const PAGE_SIZE = 20
const SEARCH_DEBOUNCE_MS = 400

/** H5 CRM 列表页通用逻辑（对齐 leads.vue 工具栏 + 筛选 + 列设置 + 视图） */
export function useCrmEntityListPage(options) {
  const {
    entityType,
    allViewLabel,
    fetchList,
    enableSearch = true,
    enableFilter = true,
    enableColumns = true,
    extraParams = () => ({}),
  } = options

  const { loadMembers } = useTeamMembers()
  const { listColumns, fields, loadListColumns, loadColumnSettingsDraft, saveListColumns, applyListColumns, formatCell, loadSchema } =
    useEntitySchema(entityType)

  const loading = ref(false)
  const loadingMore = ref(false)
  const items = ref([])
  const total = ref(0)
  const page = ref(1)
  const permissions = ref([])
  const views = ref([])
  const activeViewId = ref('')
  const viewPickerVisible = ref(false)
  const filterVisible = ref(false)
  const advancedFilters = ref(emptyFilters())
  const filterDraft = ref([createEmptyCondition()])
  const searchKeyword = ref('')
  const appliedSearchKeyword = ref('')
  let searchDebounceTimer = null
  const selectSheet = ref({ visible: false, kind: '', rowIdx: -1, options: [], tempValue: '' })
  const columnVisible = ref(false)
  const columnDraft = ref([])
  const columnSaving = ref(false)

  const hasActiveFilter = computed(
    () =>
      !activeViewId.value &&
      (countActiveFilters(advancedFilters.value) > 0 || !!appliedSearchKeyword.value.trim()),
  )
  const filterableFields = computed(() => getFilterableFields(fields.value))
  const fieldMap = computed(() => Object.fromEntries((fields.value || []).map((f) => [f.field_key, f])))
  const filterSummary = computed(() => summarizeFilters(advancedFilters.value, fieldMap.value))
  const advancedFilterCount = computed(() => countActiveFilters(advancedFilters.value))
  const hasMore = computed(() => items.value.length < total.value)
  const modalOpen = computed(() => viewPickerVisible.value || columnVisible.value || filterVisible.value)
  const columnVisibleCount = computed(() => columnDraft.value.filter((c) => c.visible !== false).length)

  async function fetchPage(pageNum, append = false) {
    const params = { page: pageNum, page_size: PAGE_SIZE, ...extraParams() }
    if (activeViewId.value) {
      params.view_id = activeViewId.value
    } else {
      const filtersParam = filtersPayloadForApi(advancedFilters.value, fields.value)
      if (filtersParam) params.filters = filtersParam
      const q = appliedSearchKeyword.value.trim()
      if (q) params.q = q
    }
    const data = await fetchList(params)
    total.value = data?.total ?? 0
    const rows = data?.items || []
    items.value = append ? [...items.value, ...rows] : rows
    page.value = pageNum
    if (!append && data?.list_fields?.length) {
      applyListColumns(data.list_fields)
    }
  }

  async function loadData() {
    loading.value = true
    try {
      const user = await ensureSession()
      permissions.value = user?.permissions || []
      try {
        views.value = await crmApi.listViews(entityType)
        if (!Array.isArray(views.value)) views.value = []
      } catch {
        views.value = []
      }
      await Promise.all([loadListColumns(), loadSchema(), loadMembers()])
      await fetchPage(1, false)
    } catch (e) {
      uni.showToast({ title: e.message || '加载失败', icon: 'none' })
    } finally {
      loading.value = false
    }
  }

  function currentViewLabel() {
    if (!activeViewId.value) return allViewLabel
    const found = views.value.find((v) => v.id === activeViewId.value)
    return found?.name || '已选视图'
  }

  function openViewPicker() {
    viewPickerVisible.value = true
  }

  function selectView(viewId) {
    activeViewId.value = viewId
    if (viewId) {
      searchKeyword.value = ''
      appliedSearchKeyword.value = ''
      if (searchDebounceTimer) {
        clearTimeout(searchDebounceTimer)
        searchDebounceTimer = null
      }
      advancedFilters.value = emptyFilters()
    }
    viewPickerVisible.value = false
    page.value = 1
    loadData()
  }

  function openFilter() {
    if (!enableFilter) return
    if (activeViewId.value) {
      uni.showToast({ title: `已选视图时请先切回${allViewLabel}`, icon: 'none' })
      return
    }
    closeSelectSheet()
    filterDraft.value = draftFromFilters(advancedFilters.value)
    filterVisible.value = true
  }

  function fieldLabel(key) {
    return fieldMap.value[key]?.label || key || '请选择字段'
  }

  function opLabel(row) {
    const def = fieldMap.value[row.field_key]
    return opsForFieldType(def?.field_type).find((o) => o.value === row.op)?.label || '条件'
  }

  function onFilterFieldPick(idx, fieldKey) {
    const field = filterableFields.value.find((f) => f.field_key === fieldKey)
    if (!field) return
    const ops = opsForFieldType(field.field_type)
    filterDraft.value[idx] = { field_key: field.field_key, op: ops[0]?.value || 'contains', value: '' }
  }

  function onFilterOpPick(idx, op) {
    const row = filterDraft.value[idx]
    filterDraft.value[idx] = { ...row, op, value: op === 'is_empty' ? '' : row.value }
  }

  function onFilterValuePick(idx, value) {
    const row = filterDraft.value[idx]
    filterDraft.value[idx] = { ...row, value }
  }

  function openSelectSheet(kind, rowIdx) {
    const row = filterDraft.value[rowIdx]
    let sheetOptions = []
    if (kind === 'field') {
      sheetOptions = filterableFields.value.map((f) => ({ label: f.label, value: f.field_key }))
    } else if (kind === 'op') {
      if (!row.field_key) return
      sheetOptions = opsForFieldType(fieldMap.value[row.field_key]?.field_type).map((o) => ({
        label: o.label,
        value: o.value,
      }))
    } else if (kind === 'value') {
      sheetOptions = (fieldMap.value[row.field_key]?.options || []).map((v) => ({ label: v, value: v }))
    }
    if (!sheetOptions.length) return
    selectSheet.value = {
      visible: true,
      kind,
      rowIdx,
      options: sheetOptions,
      tempValue: kind === 'field' ? row.field_key : kind === 'op' ? row.op : row.value,
    }
  }

  function closeSelectSheet() {
    selectSheet.value = { ...selectSheet.value, visible: false }
  }

  function pickSheetOption(value) {
    selectSheet.value = { ...selectSheet.value, tempValue: value }
  }

  function confirmSelectSheet() {
    const { kind, rowIdx, tempValue } = selectSheet.value
    if (kind === 'field') onFilterFieldPick(rowIdx, tempValue)
    else if (kind === 'op') onFilterOpPick(rowIdx, tempValue)
    else if (kind === 'value') onFilterValuePick(rowIdx, tempValue)
    closeSelectSheet()
  }

  function addFilterRow() {
    filterDraft.value.push(createEmptyCondition())
  }

  function removeFilterRow(idx) {
    filterDraft.value.splice(idx, 1)
    if (!filterDraft.value.length) filterDraft.value.push(createEmptyCondition())
  }

  function applyFilter() {
    advancedFilters.value = buildFiltersPayload(filterDraft.value, filterableFields.value)
    filterVisible.value = false
    page.value = 1
    loadData()
  }

  function resetFilter() {
    filterDraft.value = [createEmptyCondition()]
  }

  async function reloadList() {
    loading.value = true
    try {
      await fetchPage(1, false)
    } catch (e) {
      uni.showToast({ title: e.message || '加载失败', icon: 'none' })
    } finally {
      loading.value = false
    }
  }

  function flushSearch(immediate = false) {
    if (!enableSearch) return
    const run = () => {
      const next = searchKeyword.value.trim()
      if (next === appliedSearchKeyword.value) return
      appliedSearchKeyword.value = next
      if (activeViewId.value) activeViewId.value = ''
      page.value = 1
      reloadList()
    }
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
      searchDebounceTimer = null
    }
    if (immediate) {
      run()
      return
    }
    searchDebounceTimer = setTimeout(run, SEARCH_DEBOUNCE_MS)
  }

  if (enableSearch) {
    watch(searchKeyword, () => flushSearch(false))
  }

  function clearSearch() {
    searchKeyword.value = ''
    flushSearch(true)
  }

  function applySearch() {
    flushSearch(true)
  }

  function clearAllFilters() {
    advancedFilters.value = emptyFilters()
    searchKeyword.value = ''
    appliedSearchKeyword.value = ''
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
      searchDebounceTimer = null
    }
    filterDraft.value = [createEmptyCondition()]
    activeViewId.value = ''
    page.value = 1
    loadData()
  }

  async function loadMore() {
    if (loading.value || loadingMore.value || !hasMore.value) return
    loadingMore.value = true
    try {
      await fetchPage(page.value + 1, true)
    } catch (e) {
      uni.showToast({ title: e.message || '加载失败', icon: 'none' })
    } finally {
      loadingMore.value = false
    }
  }

  function reorderColumns(from, to) {
    if (from === to || from < 0 || to < 0 || from >= columnDraft.value.length || to >= columnDraft.value.length) return
    const next = [...columnDraft.value]
    const [moved] = next.splice(from, 1)
    next.splice(to, 0, moved)
    columnDraft.value = next
  }

  function jumpColumnOrder(fromIdx, raw) {
    const pos = Number(raw)
    if (!Number.isFinite(pos) || pos < 1) return
    const targetIdx = Math.round(pos) - 1
    reorderColumns(fromIdx, Math.max(0, Math.min(targetIdx, columnDraft.value.length - 1)))
  }

  async function openColumnSettings() {
    if (!enableColumns) return
    try {
      columnDraft.value = await loadColumnSettingsDraft()
      columnVisible.value = true
    } catch (e) {
      uni.showToast({ title: e.message || '加载列设置失败', icon: 'none' })
    }
  }

  function toggleColumn(col) {
    if (col.list_locked) return
    col.visible = !col.visible
  }

  async function submitColumnSettings() {
    columnSaving.value = true
    try {
      const columns = columnDraft.value.map((c, i) => ({
        field_key: c.field_key,
        label: c.label,
        visible: c.visible !== false,
        order: i,
      }))
      await saveListColumns(columns)
      uni.showToast({ title: '列设置已保存', icon: 'success' })
      columnVisible.value = false
      await fetchPage(1, false)
    } catch (e) {
      uni.showToast({ title: e.message || '保存失败', icon: 'none' })
    } finally {
      columnSaving.value = false
    }
  }

  function canCreate(permission) {
    return permission ? hasPermission(permissions.value, permission) : false
  }

  return {
    permissions,
    loading,
    loadingMore,
    items,
    total,
    hasMore,
    views,
    activeViewId,
    viewPickerVisible,
    filterVisible,
    advancedFilters,
    filterDraft,
    searchKeyword,
    appliedSearchKeyword,
    selectSheet,
    columnVisible,
    columnDraft,
    columnSaving,
    listColumns,
    fields,
    formatCell,
    hasActiveFilter,
    filterableFields,
    fieldMap,
    filterSummary,
    advancedFilterCount,
    modalOpen,
    columnVisibleCount,
    loadData,
    loadMore,
    currentViewLabel,
    openViewPicker,
    selectView,
    openFilter,
    fieldLabel,
    opLabel,
    openSelectSheet,
    closeSelectSheet,
    pickSheetOption,
    confirmSelectSheet,
    addFilterRow,
    removeFilterRow,
    applyFilter,
    resetFilter,
    clearSearch,
    applySearch,
    clearAllFilters,
    openColumnSettings,
    toggleColumn,
    jumpColumnOrder,
    submitColumnSettings,
    canCreate,
  }
}
