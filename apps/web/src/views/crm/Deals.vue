<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useEntitySchema } from '../../composables/useEntitySchema'
import { useCrmListColumns } from '../../composables/useCrmListColumns'
import { isDealColumnSortable } from '../../composables/useCrmListSort'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { notifyPinnedViewsChanged } from '../../composables/usePinnedViews'
import { navigateToView } from '../../composables/useCrmSavedViews'
import CrmColumnSettingsDialog from '../../components/crm/CrmColumnSettingsDialog.vue'
import DealFormDialog from './DealFormDialog.vue'
import CrmViewSwitcher from '../../components/crm/CrmViewSwitcher.vue'
import CrmListToolbar from '../../components/crm/CrmListToolbar.vue'
import CrmAdvancedFilterDialog from '../../components/crm/CrmAdvancedFilterDialog.vue'
import DealKanban from './DealKanban.vue'
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
  useEntitySchema('deal')
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

// 视图模式：table / kanban
const viewMode = ref(localStorage.getItem('crm_deals_view_mode') || 'table')

const pipelines = ref([])
const stageFilter = ref('')

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

const canCreate = () => hasPermission(auth.permissions, 'crm.deal.create')
const canDelete = () => hasPermission(auth.permissions, 'crm.deal.delete')
const canEdit = () => hasPermission(auth.permissions, 'crm.deal.edit')

const selectedIds = ref([])
const batchVisible = ref(false)
const batchForm = ref({ owner_user_id: '', stage_id: '', status: '' })

function onSelectionChange(rows) {
  selectedIds.value = (rows || []).map((r) => r.id)
}

function openBatch() {
  if (!selectedIds.value.length) { ElMessage.warning('请先勾选商机'); return }
  batchForm.value = { owner_user_id: '', stage_id: '', status: '' }
  batchVisible.value = true
}

async function submitBatch() {
  const payload = { deal_ids: selectedIds.value }
  if (batchForm.value.owner_user_id) payload.owner_user_id = batchForm.value.owner_user_id
  if (batchForm.value.stage_id) payload.stage_id = batchForm.value.stage_id
  if (batchForm.value.status) payload.status = batchForm.value.status
  if (!payload.owner_user_id && !payload.stage_id && !payload.status) {
    ElMessage.warning('请至少选择一项要修改的内容'); return
  }
  try {
    const { data } = await crmApi.batchUpdateDeals(payload)
    ElMessage.success(`已更新 ${data?.updated ?? 0} 条商机`)
    batchVisible.value = false
    selectedIds.value = []
    loadDeals()
  } catch (e) {
    ElMessage.error(e.message || '批量更新失败')
  }
}
const canSaveView = () => hasPermission(auth.permissions, 'crm.view.save_own')
const canManagePublic = () => hasPermission(auth.permissions, 'crm.view.manage_public')

const stageMap = computed(() => {
  const m = {}
  for (const p of pipelines.value) {
    for (const s of p.stages || []) {
      m[s.id] = { ...s, pipeline_name: p.name }
    }
  }
  return m
})

async function loadPipelines() {
  try {
    const { data } = await crmApi.listPipelines()
    pipelines.value = Array.isArray(data) ? data : []
  } catch {
    pipelines.value = []
  }
}

async function loadViews() {
  try {
    const { data } = await crmApi.listViews('deal')
    views.value = Array.isArray(data) ? data : []
    const defaultView = views.value.find((v) => v.is_default && v.owner_user_id === auth.user?.id)
    if (defaultView && !activeViewId.value) {
      activeViewId.value = defaultView.id
    }
  } catch {
    views.value = []
  }
}

async function loadDeals() {
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
      if (stageFilter.value) params.stage_id = stageFilter.value
    }
    const { data } = await crmApi.listDeals(params)
    if (filtersParam && data.filters_applied !== true) {
      ElMessage.warning('高级筛选未生效，请确认 API 已重启')
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
    loadDeals()
  }
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  if (immediate) run()
  else searchDebounceTimer = setTimeout(run, SEARCH_DEBOUNCE_MS)
}

function onSearch() { flushSearch(true) }
function onSearchClear() {
  if (searchDebounceTimer) { clearTimeout(searchDebounceTimer); searchDebounceTimer = null }
  appliedSearchKeyword.value = ''
  page.value = 1
  loadDeals()
}

watch(searchKeyword, () => {
  if (activeViewId.value) return
  flushSearch(false)
})

function onSortChange({ prop, order }) {
  if (sortDisabled.value) return
  if (!order) { sortBy.value = ''; sortDir.value = 'desc' }
  else { sortBy.value = prop; sortDir.value = order === 'ascending' ? 'asc' : 'desc' }
  page.value = 1
  loadDeals()
}

async function openColumnSettings() {
  try {
    columnDraft.value = await loadColumnSettingsDraft()
    columnVisible.value = true
  } catch (e) { ElMessage.error(e.message || '加载列设置失败') }
}

async function submitColumnSettings() {
  try {
    const columns = columnDraft.value.map((c, i) => ({ field_key: c.field_key, visible: c.visible, order: i }))
    await saveListColumns(columns)
    ElMessage.success('列设置已保存')
    columnVisible.value = false
    loadDeals()
  } catch (e) { ElMessage.error(e.message || '保存失败') }
}

function onViewChange() {
  advancedFilters.value = emptyFilters()
  searchKeyword.value = ''
  appliedSearchKeyword.value = ''
  if (searchDebounceTimer) { clearTimeout(searchDebounceTimer); searchDebounceTimer = null }
  sortBy.value = ''; sortDir.value = 'desc'
  page.value = 1
  loadDeals()
}

function openAdvancedFilter() {
  if (activeViewId.value) { ElMessage.info('已选视图时请先切回全部商机'); return }
  advancedFilterVisible.value = true
}

function applyAdvancedFilters(payload) {
  advancedFilters.value = payload
  activeViewId.value = ''
  page.value = 1
  loadDeals()
}

function openSaveView() {
  const nameFromFilters = suggestViewNameFromFilters(advancedFilters.value, fieldMap.value)
  saveViewName.value = appliedSearchKeyword.value.trim() ? `${nameFromFilters}-搜索` : nameFromFilters
  saveViewPinned.value = false; saveViewDefault.value = false; saveViewPublic.value = false
  saveViewVisible.value = true
}

async function submitSaveView() {
  if (!saveViewName.value.trim()) { ElMessage.warning('请填写视图名称'); return }
  const filters = buildFiltersForView()
  const q = appliedSearchKeyword.value.trim()
  try {
    const { data } = await crmApi.createView({
      entity_type: 'deal',
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
    navigateToView(router, '/crm/deals', data.id)
    loadDeals()
  } catch (e) { ElMessage.error(e.message || '保存失败') }
}

function onViewsRefresh() { loadViews() }

function clearActiveView() {
  activeViewId.value = ''
  router.replace({ path: '/crm/deals' })
  onViewChange()
}

function buildFiltersForView() {
  return buildFiltersPayload(advancedFilters.value.conditions || [], fields.value)
}

function clearTemporaryFilters() {
  advancedFilters.value = emptyFilters()
  searchKeyword.value = ''
  appliedSearchKeyword.value = ''
  if (searchDebounceTimer) { clearTimeout(searchDebounceTimer); searchDebounceTimer = null }
  stageFilter.value = ''
  page.value = 1
  loadDeals()
}

function openCreate() { createVisible.value = true }

function goDetail(row) { router.push(`/crm/deals/${row.id}`) }

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除商机「${row.title}」？`, '删除')
    await crmApi.deleteDeal(row.id)
    ElMessage.success('已删除')
    loadDeals()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function onPageChange(p) { page.value = p; loadDeals() }

function setViewMode(mode) {
  viewMode.value = mode
  localStorage.setItem('crm_deals_view_mode', mode)
  if (mode === 'kanban') {
    // 看板需要拉全量（不分页），DealKanban 内部自行加载
  }
}

function formatAmount(row) {
  const v = Number(row.amount || 0)
  return v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function stageLabel(row) {
  return stageMap.value[row.stage_id]?.name || row.stage_id
}

function statusTagType(status) {
  if (status === 'won') return 'success'
  if (status === 'lost') return 'danger'
  if (status === 'abandoned') return 'info'
  return ''
}

onMounted(async () => {
  if (route.query.view_id) activeViewId.value = String(route.query.view_id)
  await Promise.all([loadListColumns(), loadMembers(), loadSchema(), loadPipelines()])
  await loadViews()
  if (!activeViewId.value && route.query.view_id) activeViewId.value = String(route.query.view_id)
  loadDeals()
})

watch(() => route.query.view_id, (viewId) => {
  activeViewId.value = viewId ? String(viewId) : ''
  page.value = 1
  loadDeals()
})

onBeforeUnmount(() => {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
})
</script>

<template>
  <div class="page-card">
    <CrmListToolbar
      title="商机"
      :active-view="activeView"
      :filters-locked="!!activeViewId"
      :show-filter-hint="hasTemporaryFilter"
      @clear-view="clearActiveView"
      @clear-filters="clearTemporaryFilters"
    >
      <template #actions>
        <el-radio-group v-model="viewMode" size="small" @change="setViewMode">
          <el-radio-button value="table">表格</el-radio-button>
          <el-radio-button value="kanban">看板</el-radio-button>
        </el-radio-group>
        <el-button v-if="canEdit() && viewMode === 'table'" :disabled="!selectedIds.length" @click="openBatch">批量操作</el-button>
        <el-button @click="openColumnSettings" v-if="viewMode === 'table'">列设置</el-button>
        <el-button v-if="canCreate()" type="primary" @click="openCreate">新建商机</el-button>
      </template>

      <template #view>
        <CrmViewSwitcher
          v-model="activeViewId"
          :views="views"
          all-label="全部商机"
          list-path="/crm/deals"
          :can-save="canSaveView()"
          :has-draft-filters="hasDraftFilters"
          @change="onViewChange"
          @save="openSaveView"
          @refresh="onViewsRefresh"
        />
      </template>

      <template #filters>
        <el-select
          v-model="stageFilter"
          placeholder="按阶段筛选"
          clearable
          class="crm-stage-filter"
          :disabled="!!activeViewId"
          @change="() => { page = 1; loadDeals() }"
        >
          <el-option-group v-for="p in pipelines" :key="p.id" :label="p.name">
            <el-option v-for="s in p.stages" :key="s.id" :label="s.name" :value="s.id" />
          </el-option-group>
        </el-select>
        <el-input
          v-model="searchKeyword"
          class="crm-list-search"
          placeholder="搜索商机名称"
          prefix-icon="Search"
          clearable
          :disabled="!!activeViewId"
          @clear="onSearchClear"
          @keyup.enter="onSearch"
        />
        <el-button class="crm-adv-filter-btn" :disabled="!!activeViewId" @click="openAdvancedFilter">
          高级筛选
          <el-badge v-if="advancedFilterCount" :value="advancedFilterCount" class="crm-adv-filter-badge" />
        </el-button>
        <el-button v-if="canSaveView() && hasDraftFilters && !activeViewId" link type="primary" @click="openSaveView">
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

    <DealKanban
      v-if="viewMode === 'kanban'"
      :pipelines="pipelines"
      :stage-filter="stageFilter"
      :can-edit="canEdit()"
      @changed="loadDeals"
      @go-detail="goDetail"
    />

    <div v-else class="crm-list-table-wrap">
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
        @selection-change="onSelectionChange"
      >
        <el-table-column v-if="canEdit()" type="selection" width="42" fixed="left" @click.stop />
        <el-table-column
          v-for="col in leftFixedColumns"
          :key="col.field_key"
          :prop="col.field_key"
          :label="col.label"
          fixed="left"
          :min-width="col.width || 180"
          :sortable="!sortDisabled && isDealColumnSortable(col) ? 'custom' : false"
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
          :sortable="!sortDisabled && isDealColumnSortable(col) ? 'custom' : false"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <template v-if="col.field_key === 'stage_id'">
              <el-tag size="small" type="warning">{{ stageLabel(row) }}</el-tag>
            </template>
            <template v-else-if="col.field_key === 'status'">
              <el-tag size="small" :type="statusTagType(row.status)">{{ row.status }}</el-tag>
            </template>
            <template v-else-if="col.field_key === 'amount'">
              ¥{{ formatAmount(row) }}
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

    <div class="pager" v-if="viewMode === 'table'">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="onPageChange"
      />
    </div>

    <el-dialog v-model="batchVisible" title="批量操作" width="460px">
      <p class="deals-batch-hint">已选 {{ selectedIds.length }} 条商机，留空项不修改</p>
      <el-form label-width="88px">
        <el-form-item label="负责人">
          <el-select v-model="batchForm.owner_user_id" clearable filterable placeholder="不改" style="width: 100%">
            <el-option v-for="m in members" :key="m.user_id" :label="m.display_name || m.phone" :value="m.user_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="阶段">
          <el-select v-model="batchForm.stage_id" clearable placeholder="不改" style="width: 100%">
            <el-option-group v-for="p in pipelines" :key="p.id" :label="p.name">
              <el-option v-for="s in p.stages" :key="s.id" :label="s.name" :value="s.id" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="batchForm.status" clearable placeholder="不改" style="width: 100%">
            <el-option label="进行中 open" value="open" />
            <el-option label="in_progress" value="in_progress" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchVisible = false">取消</el-button>
        <el-button type="primary" @click="submitBatch">应用</el-button>
      </template>
    </el-dialog>

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

    <CrmColumnSettingsDialog v-model:visible="columnVisible" v-model:columns="columnDraft" @save="submitColumnSettings" />
    <DealFormDialog v-model:visible="createVisible" :pipelines="pipelines" @saved="loadDeals" />
  </div>
</template>

<style scoped>
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.crm-adv-filter-btn { position: relative; }
.crm-adv-filter-badge { margin-left: 4px; }
.crm-adv-filter-badge :deep(.el-badge__content) {
  position: static;
  transform: none;
  vertical-align: middle;
}
.crm-stage-filter { width: 180px; }
</style>
