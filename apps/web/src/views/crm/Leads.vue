<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useEntitySchema } from '../../composables/useEntitySchema'
import { useCrmListColumns } from '../../composables/useCrmListColumns'
import { isLeadColumnSortable } from '../../composables/useCrmListSort'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { notifyPinnedViewsChanged } from '../../composables/usePinnedViews'
import { navigateToView } from '../../composables/useCrmSavedViews'
import CrmImportDialog from '../../components/crm/CrmImportDialog.vue'
import CrmColumnSettingsDialog from '../../components/crm/CrmColumnSettingsDialog.vue'
import CrmEntityFormDialog from '../../components/crm/CrmEntityFormDialog.vue'
import CrmViewSwitcher from '../../components/crm/CrmViewSwitcher.vue'
import CrmListToolbar from '../../components/crm/CrmListToolbar.vue'
import CrmAdvancedFilterDialog from '../../components/crm/CrmAdvancedFilterDialog.vue'
import CrmImportHistory from './CrmImportHistory.vue'
import {
  buildFiltersPayload,
  countActiveFilters,
  emptyFilters,
  filtersPayloadForApi,
  hasActiveFilters,
  suggestViewNameFromFilters,
} from '../../utils/crmAdvancedFilter'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { listColumns, fields, loadListColumns, loadColumnSettingsDraft, saveListColumns, formatCell, applyListColumns, loadSchema } =
  useEntitySchema('lead')
const { leftFixedColumns, scrollColumns, rightFixedColumns } = useCrmListColumns(listColumns)
const { loadMembers, resolveMemberName, members } = useTeamMembers()

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const createVisible = ref(false)
const columnVisible = ref(false)
const columnDraft = ref([])
const views = ref([])
const activeViewId = ref('')
const advancedFilters = ref(emptyFilters())
const advancedFilterVisible = ref(false)
const searchKeyword = ref('')
const appliedSearchKeyword = ref('')
let searchDebounceTimer = null
const SEARCH_DEBOUNCE_MS = 400
const sortBy = ref('')
const sortDir = ref('desc')
const saveViewVisible = ref(false)
const saveViewName = ref('')
const saveViewPinned = ref(false)
const saveViewDefault = ref(false)
const saveViewPublic = ref(false)
const importVisible = ref(false)
const importHistoryVisible = ref(false)

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

const canCreate = () => hasPermission(auth.permissions, 'crm.lead.create')
const canDelete = () => hasPermission(auth.permissions, 'crm.lead.delete')
const canSaveView = () => hasPermission(auth.permissions, 'crm.view.save_own')
const canManagePublic = () => hasPermission(auth.permissions, 'crm.view.manage_public')
const canImport = () => hasPermission(auth.permissions, 'crm.lead.import')

async function loadViews() {
  try {
    const { data } = await crmApi.listViews('lead')
    views.value = Array.isArray(data) ? data : []
    const defaultView = views.value.find((v) => v.is_default && v.owner_user_id === auth.user?.id)
    if (defaultView && !activeViewId.value) {
      activeViewId.value = defaultView.id
    }
  } catch {
    views.value = []
  }
}

async function loadLeads() {
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
    }
    const { data } = await crmApi.listLeads(params)
    if (filtersParam && data.filters_applied !== true) {
      ElMessage.warning(
        '高级筛选未生效：请运行 scripts/restart-api.cmd 重启 API，并确认 Web 代理端口（VITE_API_PROXY_TARGET）与 API 一致后重启前端',
      )
    }
    items.value = data.items || []
    total.value = data.total || 0
    if (data.list_fields?.length) {
      applyListColumns(data.list_fields)
    } else if (!listColumns.value.length) {
      await loadListColumns()
    }
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
    loadLeads()
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
  loadLeads()
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
  loadLeads()
}

async function openColumnSettings() {
  try {
    columnDraft.value = await loadColumnSettingsDraft()
    columnVisible.value = true
  } catch (e) {
    ElMessage.error(e.message || '加载列设置失败')
  }
}

async function submitColumnSettings() {
  try {
    const columns = columnDraft.value.map((c, i) => ({
      field_key: c.field_key,
      visible: c.visible,
      order: i,
    }))
    await saveListColumns(columns)
    ElMessage.success('列设置已保存')
    columnVisible.value = false
    loadLeads()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
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
  page.value = 1
  loadLeads()
}

function openAdvancedFilter() {
  if (activeViewId.value) {
    ElMessage.info('已选视图时请先切回全部线索')
    return
  }
  advancedFilterVisible.value = true
}

function applyAdvancedFilters(payload) {
  advancedFilters.value = payload
  activeViewId.value = ''
  page.value = 1
  loadLeads()
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
  const filters = buildFiltersForView()
  const q = appliedSearchKeyword.value.trim()
  try {
    const { data } = await crmApi.createView({
      entity_type: 'lead',
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
    navigateToView(router, '/crm/leads', data.id)
    loadLeads()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}

function onViewsRefresh() {
  loadViews()
}

function clearActiveView() {
  activeViewId.value = ''
  router.replace({ path: '/crm/leads' })
  onViewChange()
}

function buildFiltersForView() {
  return buildFiltersPayload(advancedFilters.value.conditions || [], fields.value)
}

function clearTemporaryFilters() {
  advancedFilters.value = emptyFilters()
  searchKeyword.value = ''
  appliedSearchKeyword.value = ''
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  page.value = 1
  loadLeads()
}

function onImportCommand(command) {
  if (command === 'import') importVisible.value = true
  if (command === 'history') importHistoryVisible.value = true
}

function openCreate() {
  createVisible.value = true
}

function goDetail(row) {
  router.push(`/crm/leads/${row.id}`)
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除线索「${row.company_name}」？`, '删除')
    await crmApi.deleteLead(row.id)
    ElMessage.success('已删除')
    loadLeads()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function onPageChange(p) {
  page.value = p
  loadLeads()
}

onMounted(async () => {
  if (route.query.view_id) {
    activeViewId.value = String(route.query.view_id)
  }
  await Promise.all([loadListColumns(), loadMembers(), loadSchema()])
  await loadViews()
  if (!activeViewId.value && route.query.view_id) {
    activeViewId.value = String(route.query.view_id)
  }
  loadLeads()
})

watch(
  () => route.query.view_id,
  (viewId) => {
    activeViewId.value = viewId ? String(viewId) : ''
    page.value = 1
    loadLeads()
  },
)

onBeforeUnmount(() => {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
})
</script>

<template>
  <div class="page-card">
    <CrmListToolbar
      title="线索"
      :active-view="activeView"
      :filters-locked="!!activeViewId"
      :show-filter-hint="hasTemporaryFilter"
      @clear-view="clearActiveView"
      @clear-filters="clearTemporaryFilters"
    >
      <template #actions>
        <el-dropdown v-if="canImport()" trigger="click" @command="onImportCommand">
          <el-button>
            导入
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="import">导入线索</el-dropdown-item>
              <el-dropdown-item command="history">导入历史</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="openColumnSettings">列设置</el-button>
        <el-button v-if="canCreate()" type="primary" @click="openCreate">新建线索</el-button>
      </template>

      <template #view>
        <CrmViewSwitcher
          v-model="activeViewId"
          :views="views"
          all-label="全部线索"
          list-path="/crm/leads"
          :can-save="canSaveView()"
          :has-draft-filters="hasDraftFilters"
          @change="onViewChange"
          @save="openSaveView"
          @refresh="onViewsRefresh"
        />
      </template>

      <template #filters>
        <el-input
          v-model="searchKeyword"
          class="crm-list-search"
          placeholder="搜索公司、联系人、手机"
          prefix-icon="Search"
          clearable
          :disabled="!!activeViewId"
          @clear="onSearchClear"
          @keyup.enter="onSearch"
        />
        <el-button
          class="crm-adv-filter-btn"
          :disabled="!!activeViewId"
          @click="openAdvancedFilter"
        >
          高级筛选
          <el-badge v-if="advancedFilterCount" :value="advancedFilterCount" class="crm-adv-filter-badge" />
        </el-button>
        <el-button
          v-if="canSaveView() && hasDraftFilters && !activeViewId"
          link
          type="primary"
          @click="openSaveView"
        >
          保存为视图
        </el-button>
      </template>
    </CrmListToolbar>

    <CrmAdvancedFilterDialog
      v-model:visible="advancedFilterVisible"
      :fields="fields"
      :members="members"
      :model-value="advancedFilters"
      @apply="applyAdvancedFilters"
    />

    <div class="crm-list-table-wrap">
    <el-table
      :key="tableSortKey"
      v-loading="loading"
      :data="items"
      border
      class="crm-list-table"
      :default-sort="defaultTableSort"
      :header-cell-class-name="() => 'crm-list-table__header-cell'"
      @sort-change="onSortChange"
      @row-click="goDetail"
    >
      <el-table-column
        v-for="col in leftFixedColumns"
        :key="col.field_key"
        :prop="col.field_key"
        :label="col.label"
        fixed="left"
        :min-width="col.width || 160"
        :sortable="!sortDisabled && isLeadColumnSortable(col) ? 'custom' : false"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ formatCell(row, col.field_key, col.field_type) }}
        </template>
      </el-table-column>
      <el-table-column
        v-for="col in scrollColumns"
        :key="col.field_key"
        :prop="col.field_key"
        :label="col.label"
        :min-width="col.width || 120"
        :sortable="!sortDisabled && isLeadColumnSortable(col) ? 'custom' : false"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <template v-if="col.field_key === 'status'">
            <el-tag size="small">{{ formatCell(row, col.field_key, col.field_type) }}</el-tag>
          </template>
          <template v-else>
            {{ formatCell(row, col.field_key, col.field_type) }}
          </template>
        </template>
      </el-table-column>
      <el-table-column
        v-for="col in rightFixedColumns"
        :key="col.field_key"
        :prop="col.field_key"
        :label="col.label"
        fixed="right"
        :width="col.width || 120"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ resolveMemberName(row.owner_user_id) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="132" fixed="right" align="center" @click.stop>
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
          <el-button v-if="canDelete()" link type="danger" @click.stop="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="onPageChange"
      />
    </div>

    <el-dialog v-model="saveViewVisible" title="保存视图" width="400px">
      <el-form label-width="88px">
        <el-form-item label="名称" required>
          <el-input v-model="saveViewName" placeholder="视图名称" />
        </el-form-item>
        <el-form-item label="钉选">
          <el-checkbox v-model="saveViewPinned">钉选到侧栏</el-checkbox>
        </el-form-item>
        <el-form-item label="默认">
          <el-checkbox v-model="saveViewDefault">设为默认视图</el-checkbox>
        </el-form-item>
        <el-form-item v-if="canManagePublic()" label="公开">
          <el-checkbox v-model="saveViewPublic">团队可见</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveViewVisible = false">取消</el-button>
        <el-button type="primary" @click="submitSaveView">保存</el-button>
      </template>
    </el-dialog>

    <CrmColumnSettingsDialog
      v-model:visible="columnVisible"
      v-model:columns="columnDraft"
      @save="submitColumnSettings"
    />

    <CrmEntityFormDialog
      v-model:visible="createVisible"
      entity-type="lead"
      mode="create"
      @saved="loadLeads"
    />

    <CrmImportDialog v-model:visible="importVisible" entity-type="lead" @done="loadLeads" />
    <CrmImportHistory v-model:visible="importHistoryVisible" entity-type="lead" />
  </div>
</template>

<style scoped>
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.crm-adv-filter-btn {
  position: relative;
}

.crm-adv-filter-badge {
  margin-left: 4px;
}

.crm-adv-filter-badge :deep(.el-badge__content) {
  position: static;
  transform: none;
  vertical-align: middle;
}
</style>
