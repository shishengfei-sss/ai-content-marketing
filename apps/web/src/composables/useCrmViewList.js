import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { hasPermission } from '../config/permissions'
import { crmApi } from '../api/client'
import { notifyPinnedViewsChanged } from './usePinnedViews'
import { navigateToView } from './useCrmSavedViews'
import {
  buildFiltersPayload,
  countActiveFilters,
  emptyFilters,
  filtersPayloadForApi,
  hasActiveFilters,
  suggestViewNameFromFilters,
} from '../utils/crmAdvancedFilter'

const SEARCH_DEBOUNCE_MS = 400

/**
 * 统一封装 CRM 列表页的「视图切换 / 搜索 / 排序 / 高级筛选 / 保存视图」逻辑，
 * 使报价/合同/订单/回款等列表页与线索/商机保持一致的交互。
 *
 * @param {Object} opts
 * @param {string} opts.entityType        实体类型，如 'quote'
 * @param {string} opts.listPath          列表路由，如 '/crm/quotes'
 * @param {import('vue').Ref<Array>} opts.fields  schema 字段 ref（供高级筛选用）
 * @param {(params: Object) => Promise<{items:Array,total:number,list_fields?:Array,filters_applied?:boolean}>} opts.fetcher
 * @param {import('vue').Ref<Object>} [opts.extraParams] 额外查询参数（如 { status } ），仅在无激活视图时合并
 * @param {() => void} [opts.onResetExtra] 视图切换/清除筛选时重置额外参数的回调
 */
export function useCrmViewList({ entityType, listPath, fields, fetcher, extraParams, onResetExtra }) {
  const router = useRouter()
  const route = useRoute()
  const auth = useAuthStore()

  const loading = ref(false)
  const items = ref([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)

  const views = ref([])
  const activeViewId = ref('')
  const advancedFilters = ref(emptyFilters())
  const advancedFilterVisible = ref(false)
  const searchKeyword = ref('')
  const appliedSearchKeyword = ref('')
  let searchDebounceTimer = null
  const sortBy = ref('')
  const sortDir = ref('desc')

  const saveViewVisible = ref(false)
  const saveViewName = ref('')
  const saveViewPinned = ref(false)
  const saveViewDefault = ref(false)
  const saveViewPublic = ref(false)

  const tableSortKey = computed(() => `${sortBy.value}-${sortDir.value}`)
  const activeView = computed(
    () => views.value.find((v) => String(v.id) === String(activeViewId.value)) || null,
  )
  const hasDraftFilters = computed(
    () => hasActiveFilters(advancedFilters.value) || !!appliedSearchKeyword.value.trim(),
  )
  const hasTemporaryFilter = computed(
    () => !activeViewId.value && (hasActiveFilters(advancedFilters.value) || !!appliedSearchKeyword.value.trim()),
  )
  const advancedFilterCount = computed(() => countActiveFilters(advancedFilters.value))
  const fieldMap = computed(() => Object.fromEntries((fields.value || []).map((f) => [f.field_key, f])))
  const defaultTableSort = computed(() =>
    sortBy.value
      ? { prop: sortBy.value, order: sortDir.value === 'asc' ? 'ascending' : 'descending' }
      : undefined,
  )
  const sortDisabled = computed(() => !!activeViewId.value)

  const canSaveView = () => hasPermission(auth.permissions, 'crm.view.save_own')
  const canManagePublic = () => hasPermission(auth.permissions, 'crm.view.manage_public')

  async function loadViews() {
    try {
      const { data } = await crmApi.listViews(entityType)
      views.value = Array.isArray(data) ? data : []
      const defaultView = views.value.find((v) => v.is_default && v.owner_user_id === auth.user?.id)
      if (defaultView && !activeViewId.value) {
        activeViewId.value = defaultView.id
      }
    } catch {
      views.value = []
    }
  }

  async function load() {
    loading.value = true
    let filtersParam = null
    try {
      const params = { page: page.value, page_size: pageSize.value }
      if (activeViewId.value) {
        params.view_id = activeViewId.value
      } else {
        filtersParam = filtersPayloadForApi(advancedFilters.value, fields.value)
        if (filtersParam) params.filters = filtersParam
        const q = appliedSearchKeyword.value.trim()
        if (q) params.q = q
        if (sortBy.value) {
          params.sort_by = sortBy.value
          params.sort_dir = sortDir.value || 'desc'
        }
        if (extraParams?.value) {
          for (const [k, v] of Object.entries(extraParams.value)) {
            if (v !== '' && v != null) params[k] = v
          }
        }
      }
      const res = await fetcher(params)
      if (filtersParam && res.filters_applied !== true) {
        ElMessage.warning('高级筛选未生效：请确认 API 已重启且前端代理端口一致')
      }
      items.value = res.items || []
      total.value = res.total || 0
      return res
    } catch (e) {
      ElMessage.error(e.message || '加载失败')
    } finally {
      loading.value = false
    }
  }

  function flushSearch(immediate = false) {
    if (activeViewId.value) return
    const run = () => {
      const next = searchKeyword.value.trim()
      if (next === appliedSearchKeyword.value) return
      appliedSearchKeyword.value = next
      page.value = 1
      load()
    }
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
      searchDebounceTimer = null
    }
    if (immediate) run()
    else searchDebounceTimer = setTimeout(run, SEARCH_DEBOUNCE_MS)
  }

  function onSearch() {
    flushSearch(true)
  }

  function onSearchClear() {
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
      searchDebounceTimer = null
    }
    appliedSearchKeyword.value = ''
    page.value = 1
    load()
  }

  watch(searchKeyword, () => {
    if (activeViewId.value) return
    flushSearch(false)
  })

  function onSortChange({ prop, order }) {
    if (sortDisabled.value) return
    if (!order) {
      sortBy.value = ''
      sortDir.value = 'desc'
    } else {
      sortBy.value = prop
      sortDir.value = order === 'ascending' ? 'asc' : 'desc'
    }
    page.value = 1
    load()
  }

  function onViewChange() {
    advancedFilters.value = emptyFilters()
    searchKeyword.value = ''
    appliedSearchKeyword.value = ''
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
      searchDebounceTimer = null
    }
    sortBy.value = ''
    sortDir.value = 'desc'
    if (onResetExtra) onResetExtra()
    page.value = 1
    load()
  }

  function openAdvancedFilter() {
    if (activeViewId.value) {
      ElMessage.info('已选视图时请先切回全部')
      return
    }
    advancedFilterVisible.value = true
  }

  function applyAdvancedFilters(payload) {
    advancedFilters.value = payload
    activeViewId.value = ''
    page.value = 1
    load()
  }

  function openSaveView() {
    const nameFromFilters = suggestViewNameFromFilters(advancedFilters.value, fieldMap.value)
    saveViewName.value = appliedSearchKeyword.value.trim()
      ? `${nameFromFilters}-搜索`
      : nameFromFilters
    saveViewPinned.value = false
    saveViewDefault.value = false
    saveViewPublic.value = false
    saveViewVisible.value = true
  }

  async function submitSaveView() {
    if (!saveViewName.value.trim()) {
      ElMessage.warning('请填写视图名称')
      return
    }
    const filters = buildFiltersPayload(advancedFilters.value.conditions || [], fields.value)
    const q = appliedSearchKeyword.value.trim()
    try {
      const { data } = await crmApi.createView({
        entity_type: entityType,
        name: saveViewName.value.trim(),
        filters,
        search_q: q || null,
        is_pinned: saveViewPinned.value,
        is_default: saveViewDefault.value,
        is_public: saveViewPublic.value,
      })
      ElMessage.success('视图已保存')
      saveViewVisible.value = false
      if (saveViewPinned.value) notifyPinnedViewsChanged()
      await loadViews()
      activeViewId.value = data.id
      navigateToView(router, listPath, data.id)
      load()
    } catch (e) {
      ElMessage.error(e.message || '保存失败')
    }
  }

  function onViewsRefresh() {
    loadViews()
  }

  function clearActiveView() {
    activeViewId.value = ''
    router.replace({ path: listPath })
    onViewChange()
  }

  function clearTemporaryFilters() {
    advancedFilters.value = emptyFilters()
    searchKeyword.value = ''
    appliedSearchKeyword.value = ''
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
      searchDebounceTimer = null
    }
    if (onResetExtra) onResetExtra()
    page.value = 1
    load()
  }

  function onPageChange(p) {
    page.value = p
    load()
  }

  function initRouteView() {
    if (route.query.view_id) {
      activeViewId.value = String(route.query.view_id)
    }
  }

  function watchRouteView() {
    return watch(
      () => route.query.view_id,
      (viewId) => {
        activeViewId.value = viewId ? String(viewId) : ''
        page.value = 1
        load()
      },
    )
  }

  onBeforeUnmount(() => {
    if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  })

  return {
    // state
    loading,
    items,
    total,
    page,
    pageSize,
    views,
    activeViewId,
    advancedFilters,
    advancedFilterVisible,
    searchKeyword,
    appliedSearchKeyword,
    sortBy,
    sortDir,
    saveViewVisible,
    saveViewName,
    saveViewPinned,
    saveViewDefault,
    saveViewPublic,
    // computed
    activeView,
    hasDraftFilters,
    hasTemporaryFilter,
    advancedFilterCount,
    fieldMap,
    defaultTableSort,
    sortDisabled,
    tableSortKey,
    // permissions
    canSaveView,
    canManagePublic,
    // methods
    loadViews,
    load,
    onSearch,
    onSearchClear,
    onSortChange,
    onViewChange,
    openAdvancedFilter,
    applyAdvancedFilters,
    openSaveView,
    submitSaveView,
    onViewsRefresh,
    clearActiveView,
    clearTemporaryFilters,
    onPageChange,
    initRouteView,
    watchRouteView,
  }
}
