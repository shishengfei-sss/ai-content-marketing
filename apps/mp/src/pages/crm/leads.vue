<script setup>
import { computed, ref, watch } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { crmApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { useEntitySchema } from '@/utils/useEntitySchema'
import { LEAD_STATUS_OPTIONS } from '@/utils/crmConstants'
import { buildCardMetaItems } from '@/utils/crmListMeta'
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
const { loadMembers } = useTeamMembers()
const { listColumns, fields, loadListColumns, loadColumnSettingsDraft, saveListColumns, applyListColumns, formatCell, loadSchema } =
  useEntitySchema('lead')

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
const SEARCH_DEBOUNCE_MS = 400
const selectSheet = ref({
  visible: false,
  kind: '',
  rowIdx: -1,
  options: [],
  tempValue: '',
})

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

const showStatusInHead = computed(() =>
  listColumns.value.some((c) => c.field_key === 'status' && c.visible !== false),
)

const modalOpen = computed(
  () =>
    activityVisible.value ||
    viewPickerVisible.value ||
    columnVisible.value ||
    filterVisible.value,
)

const columnVisible = ref(false)
const columnDraft = ref([])
const columnSaving = ref(false)

const activityVisible = ref(false)
const activeLeadId = ref('')
const activityForm = ref({ activity_type: 'call', content: '', status: '' })
const activityStatusSheetVisible = ref(false)

const canCreate = () => hasPermission(permissions.value, 'crm.lead.create')
const canActivity = () => hasPermission(permissions.value, 'crm.activity.create')
const canEditLead = () => hasPermission(permissions.value, 'crm.lead.edit')

async function fetchPage(pageNum, append = false) {
  const params = { page: pageNum, page_size: PAGE_SIZE }
  if (activeViewId.value) {
    params.view_id = activeViewId.value
  } else {
    const filtersParam = filtersPayloadForApi(advancedFilters.value, fields.value)
    if (filtersParam) params.filters = filtersParam
    const q = appliedSearchKeyword.value.trim()
    if (q) params.q = q
  }
  const data = await crmApi.listLeads(params)
  total.value = data.total ?? 0
  const rows = data.items || []
  items.value = append ? [...items.value, ...rows] : rows
  page.value = pageNum
  if (!append && data.list_fields?.length) {
    applyListColumns(data.list_fields)
  }
}

function cardMetaItems(item) {
  return buildCardMetaItems(item, listColumns.value, formatCell)
}

async function loadData() {
  loading.value = true
  try {
    const user = await ensureSession()
    permissions.value = user?.permissions || []
    try {
      views.value = await crmApi.listViews('lead')
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
  if (!activeViewId.value) return '全部线索'
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
  if (activeViewId.value) {
    uni.showToast({ title: '已选视图时请先切回全部线索', icon: 'none' })
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
  filterDraft.value[idx] = {
    field_key: field.field_key,
    op: ops[0]?.value || 'contains',
    value: '',
  }
}

function onFilterOpPick(idx, op) {
  const row = filterDraft.value[idx]
  filterDraft.value[idx] = {
    ...row,
    op,
    value: op === 'is_empty' ? '' : row.value,
  }
}

function onFilterValuePick(idx, value) {
  const row = filterDraft.value[idx]
  filterDraft.value[idx] = { ...row, value }
}

function openSelectSheet(kind, rowIdx) {
  const row = filterDraft.value[rowIdx]
  let options = []
  if (kind === 'field') {
    options = filterableFields.value.map((f) => ({ label: f.label, value: f.field_key }))
  } else if (kind === 'op') {
    if (!row.field_key) return
    options = opsForFieldType(fieldMap.value[row.field_key]?.field_type).map((o) => ({
      label: o.label,
      value: o.value,
    }))
  } else if (kind === 'value') {
    options = (fieldMap.value[row.field_key]?.options || []).map((v) => ({ label: v, value: v }))
  }
  if (!options.length) return
  selectSheet.value = {
    visible: true,
    kind,
    rowIdx,
    options,
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

watch(searchKeyword, () => flushSearch(false))

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

const columnVisibleCount = computed(
  () => columnDraft.value.filter((c) => c.visible !== false).length,
)

function reorderColumns(from, to) {
  if (
    from === to ||
    from < 0 ||
    to < 0 ||
    from >= columnDraft.value.length ||
    to >= columnDraft.value.length
  ) {
    return
  }
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

function openCreate() {
  uni.navigateTo({ url: '/pages/crm/lead-create' })
}

function goDetail(item) {
  uni.navigateTo({ url: `/pages/crm/lead-detail?id=${item.id}` })
}

function openActivity(item) {
  activeLeadId.value = typeof item === 'object' ? item.id : item
  const status = typeof item === 'object' ? item.status : ''
  activityForm.value = { activity_type: 'call', content: '', status: status || '待跟进' }
  activityStatusSheetVisible.value = false
  activityVisible.value = true
}

function openActivityStatusSheet() {
  activityStatusSheetVisible.value = true
}

function closeActivityStatusSheet() {
  activityStatusSheetVisible.value = false
}

function pickActivityStatus(value) {
  activityForm.value = { ...activityForm.value, status: value }
  closeActivityStatusSheet()
}

function closeActivityModal() {
  activityVisible.value = false
  closeActivityStatusSheet()
}

async function submitActivity() {
  if (!activityForm.value.content.trim()) {
    uni.showToast({ title: '请填写跟进内容', icon: 'none' })
    return
  }
  try {
    const body = {
      lead_id: activeLeadId.value,
      activity_type: activityForm.value.activity_type,
      content: activityForm.value.content,
    }
    if (canEditLead() && activityForm.value.status) {
      body.status = activityForm.value.status
    }
    await crmApi.createActivity(body)
    uni.showToast({ title: '已添加跟进', icon: 'success' })
    closeActivityModal()
    loadData()
  } catch (e) {
    uni.showToast({ title: e.message || '添加失败', icon: 'none' })
  }
}

onShow(loadData)
</script>

<template>
  <view class="page">
    <view class="toolbar">
      <view class="toolbar__search-row">
        <view class="search-box">
          <text class="search-box__icon">⌕</text>
          <input
            v-model="searchKeyword"
            class="search-input"
            type="text"
            placeholder="搜索公司、联系人、手机"
            confirm-type="search"
            :adjust-position="true"
            @confirm="applySearch"
          />
          <text v-if="searchKeyword" class="search-clear" @tap="clearSearch">×</text>
        </view>
        <view
          class="toolbar-btn toolbar-btn--filter"
          :class="{ 'toolbar-btn--filter-active': advancedFilterCount > 0 || filterVisible }"
          @tap="openFilter"
        >
          <text class="toolbar-btn__text">筛选</text>
          <text v-if="advancedFilterCount" class="toolbar-btn__badge">{{ advancedFilterCount }}</text>
        </view>
      </view>

      <view v-if="hasActiveFilter" class="filter-tags">
        <text v-for="(tag, i) in filterSummary" :key="i" class="filter-tag">{{ tag }}</text>
        <text v-if="appliedSearchKeyword.trim()" class="filter-tag">搜索：{{ appliedSearchKeyword.trim() }}</text>
        <text class="filter-tag filter-tag--clear" @tap="clearAllFilters">清除</text>
      </view>

      <view class="toolbar__action-row">
        <view class="view-chip" @tap="openViewPicker">
          <text class="view-chip__text">{{ currentViewLabel() }}</text>
          <text class="view-chip__count">{{ loading ? '…' : total }}</text>
          <text class="view-chip__arrow">▾</text>
        </view>
        <view class="toolbar__actions">
          <view class="toolbar-btn" @tap="openColumnSettings">
            <text class="toolbar-btn__icon toolbar-btn__icon--sm">☰</text>
            <text class="toolbar-btn__text">列设置</text>
          </view>
          <view v-if="canCreate()" class="toolbar-btn toolbar-btn--primary" @tap="openCreate">
            <text class="toolbar-btn__icon">+</text>
            <text class="toolbar-btn__text">新建</text>
          </view>
        </view>
      </view>
    </view>

    <scroll-view
      scroll-y
      class="scroll"
      :class="{ 'scroll--locked': modalOpen }"
      :lower-threshold="100"
      @scrolltolower="loadMore"
    >
      <view v-if="loading" class="empty">加载中…</view>
      <view v-else-if="!items.length" class="empty">暂无线索</view>
      <view v-else class="list">
        <view v-for="item in items" :key="item.id" class="card" @click="goDetail(item)">
          <view class="card__head">
            <view class="card__title-wrap">
              <text class="card__title">{{ item.company_name }}</text>
              <text v-if="showStatusInHead" class="status">{{ item.status }}</text>
            </view>
          </view>
          <view v-if="cardMetaItems(item).length" class="card__meta">
            <view v-for="meta in cardMetaItems(item)" :key="meta.field_key" class="card__meta-row">
              <text class="card__meta-label">{{ meta.label }}</text>
              <text class="card__meta-value">{{ meta.value }}</text>
            </view>
          </view>
          <text v-else class="card__meta card__meta--empty">暂无更多信息</text>
          <view v-if="canActivity()" class="card__foot" @click.stop>
            <view class="card__actions">
              <view class="card__action" @tap="openActivity(item)">写跟进</view>
              <view class="card__action card__action--ghost" @tap="goDetail(item)">详情</view>
            </view>
          </view>
        </view>
        <view v-if="loadingMore" class="list-foot">加载中…</view>
        <view v-else-if="!hasMore && items.length" class="list-foot">没有更多了</view>
      </view>
    </scroll-view>

    <view v-if="activityVisible" class="mask" @tap.self="closeActivityModal">
      <view class="dialog" @tap.stop>
        <text class="dialog__title">写跟进</text>
        <textarea
          v-model="activityForm.content"
          class="textarea"
          placeholder="跟进内容"
          :adjust-position="true"
          :cursor-spacing="20"
        />
        <view
          v-if="canEditLead()"
          class="status-pick"
          @tap="openActivityStatusSheet"
        >
          <text class="status-pick__label">线索状态</text>
          <text class="status-pick__value">{{ activityForm.status || '请选择' }}</text>
          <text class="status-pick__arrow">▾</text>
        </view>
        <view class="dialog__acts">
          <button class="btn" hover-class="none" @tap="closeActivityModal">取消</button>
          <button class="btn btn--primary" hover-class="none" @tap="submitActivity">提交</button>
        </view>
      </view>

      <view v-if="activityStatusSheetVisible" class="select-sheet" @tap.stop>
        <view class="select-sheet__bar">
          <text class="select-sheet__cancel" @tap="closeActivityStatusSheet">取消</text>
          <text class="select-sheet__title">选择线索状态</text>
          <text class="select-sheet__ok" @tap="closeActivityStatusSheet">完成</text>
        </view>
        <scroll-view scroll-y class="select-sheet__scroll">
          <view
            v-for="opt in LEAD_STATUS_OPTIONS"
            :key="opt"
            class="select-sheet__opt"
            :class="{ 'select-sheet__opt--active': opt === activityForm.status }"
            @tap="pickActivityStatus(opt)"
          >
            {{ opt }}
          </view>
        </scroll-view>
      </view>
    </view>
    <view v-if="viewPickerVisible" class="mask" @tap.self="viewPickerVisible = false">
      <view class="dialog dialog--tall" @tap.stop>
        <text class="dialog__title">切换视图</text>
        <scroll-view scroll-y class="column-scroll">
          <view class="column-item" @tap="selectView('')">
            <text>全部线索</text>
          </view>
          <view v-for="view in views" :key="view.id" class="column-item" @tap="selectView(view.id)">
            <text>{{ view.name }}</text>
          </view>
        </scroll-view>
      </view>
    </view>

    <view v-if="filterVisible" class="mask" @tap.self="filterVisible = false; closeSelectSheet()">
      <view class="dialog dialog--tall" @tap.stop>
        <text class="dialog__title">高级筛选</text>
        <text class="filter-tip">满足以下全部条件（AND）</text>
        <scroll-view scroll-y class="column-scroll">
          <view v-for="(row, idx) in filterDraft" :key="idx" class="adv-filter-row">
            <view class="adv-filter-pick" @tap="openSelectSheet('field', idx)">
              {{ fieldLabel(row.field_key) }}
            </view>
            <view
              v-if="row.field_key"
              class="adv-filter-pick adv-filter-pick--sm"
              @tap="openSelectSheet('op', idx)"
            >
              {{ opLabel(row) }}
            </view>
            <view
              v-if="row.field_key && row.op !== 'is_empty' && fieldMap[row.field_key]?.field_type === 'select'"
              class="adv-filter-pick"
              @tap="openSelectSheet('value', idx)"
            >
              {{ row.value || '请选择值' }}
            </view>
            <input
              v-else-if="row.field_key && row.op !== 'is_empty'"
              v-model="row.value"
              class="adv-filter-input"
              type="text"
              placeholder="请输入"
            />
            <text v-else-if="row.field_key && row.op === 'is_empty'" class="adv-filter-empty">无需填写</text>
            <text class="adv-filter-remove" @tap="removeFilterRow(idx)">删除</text>
          </view>
          <view class="adv-filter-add" @tap="addFilterRow">+ 添加条件</view>
        </scroll-view>
        <view class="dialog__acts">
          <button class="btn" hover-class="none" @tap="resetFilter">重置</button>
          <button class="btn btn--primary" hover-class="none" @tap="applyFilter">确定</button>
        </view>
      </view>

      <view v-if="selectSheet.visible" class="select-sheet" @tap.stop>
        <view class="select-sheet__bar">
          <text class="select-sheet__cancel" @tap="closeSelectSheet">取消</text>
          <text class="select-sheet__ok" @tap="confirmSelectSheet">完成</text>
        </view>
        <scroll-view scroll-y class="select-sheet__scroll">
          <view
            v-for="opt in selectSheet.options"
            :key="String(opt.value)"
            class="select-sheet__opt"
            :class="{ 'select-sheet__opt--active': opt.value === selectSheet.tempValue }"
            @tap="pickSheetOption(opt.value)"
          >
            {{ opt.label }}
          </view>
        </scroll-view>
      </view>
    </view>

    <view v-if="columnVisible" class="mask" @tap.self="columnVisible = false">
      <view class="dialog dialog--tall" @tap.stop>
        <text class="dialog__title">列设置</text>
        <text class="column-settings-tip">
          勾选控制是否在列表中显示；输入目标序号后点击其他区域生效（序号越小越靠前）。带「固定」标签的列无法隐藏
        </text>
        <text class="column-settings-meta">
          已显示 {{ columnVisibleCount }} / {{ columnDraft.length }} 列
        </text>
        <scroll-view scroll-y class="column-scroll">
          <view v-if="!columnDraft.length" class="empty">暂无可用列</view>
          <view v-else class="column-settings-table">
            <view class="column-settings-head">
              <text class="column-settings-head__show">显示</text>
              <text class="column-settings-head__name">列名</text>
              <text class="column-settings-head__order">序号</text>
            </view>
            <view
              v-for="(col, idx) in columnDraft"
              :key="col.field_key"
              class="column-settings-row"
              :class="{ 'column-settings-row--locked': col.list_locked, 'column-settings-row--hidden': col.visible === false }"
            >
              <checkbox
                :checked="col.visible !== false"
                :disabled="col.list_locked"
                class="column-settings-check"
                @click.stop="toggleColumn(col)"
              />
              <view class="column-settings-name">
                <text class="column-settings-label">{{ col.label }}</text>
                <text v-if="col.list_locked" class="column-settings-tag">固定</text>
              </view>
              <input
                type="text"
                inputmode="numeric"
                class="column-settings-order"
                :value="String(idx + 1)"
                @click.stop
                @confirm="(e) => jumpColumnOrder(idx, e.detail.value)"
                @blur="(e) => jumpColumnOrder(idx, e.detail.value)"
              />
            </view>
          </view>
        </scroll-view>
        <view class="dialog__acts">
          <button class="btn" hover-class="none" :disabled="columnSaving" @tap="columnVisible = false">
            取消
          </button>
          <button
            class="btn btn--primary"
            hover-class="none"
            :disabled="columnSaving"
            @tap="submitColumnSettings"
          >
            {{ columnSaving ? '保存中…' : '保存' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
  padding: 12px;
  box-sizing: border-box;
}

.toolbar {
  flex-shrink: 0;
  margin-bottom: 12px;
  padding: 14px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}

.toolbar__search-row {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.search-box {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  min-width: 0;
  height: 36px;
  padding: 0 10px 0 34px;
  border-radius: 8px;
  background: #f5f7fa;
  border: 1px solid #eef2f6;
  box-sizing: border-box;
}

.search-box__icon {
  position: absolute;
  left: 12px;
  color: #94a3b8;
  font-size: 15px;
  line-height: 1;
}

.search-input {
  width: 100%;
  height: 36px;
  padding: 0 24px 0 0;
  border: none;
  background: transparent;
  font-size: 14px;
  box-sizing: border-box;
  color: #1e293b;
}

.search-clear {
  position: absolute;
  right: 8px;
  width: 20px;
  height: 20px;
  line-height: 18px;
  text-align: center;
  color: #94a3b8;
  font-size: 16px;
  border-radius: 50%;
  background: #e2e8f0;
}

/* 统一工具栏按钮：筛选 / 列设置 / 新建 同高同圆角 */
.toolbar-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 36px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  font-size: 13px;
  box-sizing: border-box;
  position: relative;
}

.toolbar-btn--filter {
  min-width: 56px;
  border-color: #dbeafe;
  color: #1677ff;
}

.toolbar-btn--filter-active {
  background: #e6f4ff;
  border-color: #91caff;
}

.toolbar-btn--primary {
  border-color: #1677ff;
  background: #1677ff;
  color: #fff;
}

.toolbar-btn__icon {
  font-size: 15px;
  line-height: 1;
  font-weight: 600;
}

.toolbar-btn__icon--sm {
  font-size: 13px;
  font-weight: 400;
}

.toolbar-btn__text {
  font-size: 13px;
  line-height: 1;
  white-space: nowrap;
}

.toolbar-btn__badge {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 16px;
  height: 16px;
  line-height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: #1677ff;
  color: #fff;
  font-size: 10px;
  text-align: center;
  border: 2px solid #fff;
  box-sizing: border-box;
}

.toolbar__action-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.view-chip {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 12px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  box-sizing: border-box;
}

.view-chip__text {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.view-chip__count {
  flex-shrink: 0;
  height: 20px;
  line-height: 20px;
  padding: 0 7px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #64748b;
  font-size: 11px;
  font-weight: 500;
}

.view-chip__arrow {
  flex-shrink: 0;
  font-size: 11px;
  color: #94a3b8;
}

.toolbar__actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.adv-filter-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 0;
  border-bottom: 1px solid #f1f5f9;
}

.adv-filter-pick {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  color: #334155;
  background: #fff;
  cursor: pointer;
}

.adv-filter-pick--sm {
  color: #64748b;
}

.adv-filter-input {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  background: #fff;
}

.adv-filter-empty {
  font-size: 13px;
  color: #94a3b8;
}

.adv-filter-remove {
  align-self: flex-end;
  color: #ef4444;
  font-size: 13px;
}

.adv-filter-add {
  padding: 14px 0;
  color: #1677ff;
  font-size: 14px;
}

.filter-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  flex-shrink: 0;
}

.filter-tag {
  padding: 4px 10px;
  border-radius: 999px;
  background: #e6f4ff;
  color: #1677ff;
  font-size: 12px;
}

.filter-tag--clear {
  background: #f1f5f9;
  color: #64748b;
}

.filter-tip {
  display: block;
  margin-bottom: 12px;
  font-size: 12px;
  color: #64748b;
}

.filter-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.filter-option {
  padding: 8px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  font-size: 14px;
  color: #475569;
  background: #fff;
}

.filter-option--active {
  border-color: #1677ff;
  background: #e6f4ff;
  color: #1677ff;
}

.scroll {
  flex: 1;
  min-height: 0;
}

.scroll--locked {
  pointer-events: none;
}

.list-foot {
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  padding: 16px 0;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card {
  background: #fff;
  border-radius: 12px;
  padding: 14px 16px 12px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
  border: 1px solid #f1f5f9;
}

.card__head {
  margin-bottom: 2px;
}

.card__title-wrap {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.card__title {
  flex: 1;
  min-width: 0;
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  line-height: 1.35;
}

.status {
  flex-shrink: 0;
  font-size: 11px;
  color: #1677ff;
  background: #e6f4ff;
  padding: 3px 10px;
  border-radius: 999px;
  line-height: 1.4;
  font-weight: 500;
}

.card__meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 0 0;
  margin-top: 10px;
  border-top: 1px solid #f1f5f9;
}

.card__meta--empty {
  display: block;
  padding-top: 12px;
  margin-top: 10px;
  border-top: 1px solid #f1f5f9;
  color: #94a3b8;
  font-size: 13px;
}

.card__meta-row {
  display: grid;
  grid-template-columns: 4.5em 1fr;
  gap: 8px;
  font-size: 13px;
  line-height: 1.45;
  align-items: start;
}

.card__meta-label {
  color: #94a3b8;
}

.card__meta-value {
  color: #334155;
  word-break: break-all;
}

.card__foot {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.card__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card__action {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 34px;
  border-radius: 8px;
  background: #1677ff;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
}

.card__action--ghost {
  background: #f8fafc;
  color: #475569;
  border: 1px solid #e2e8f0;
}

.column-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 14px;
}

.column-item--locked {
  opacity: 0.92;
}

.column-item__tag {
  margin-left: auto;
  padding: 2px 8px;
  border-radius: 10px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 12px;
}

.column-settings-tip {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.column-settings-meta {
  display: block;
  margin-bottom: 10px;
  font-size: 12px;
  color: #94a3b8;
}

.column-settings-table {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
}

.column-settings-head,
.column-settings-row {
  display: grid;
  grid-template-columns: 44px 1fr 64px;
  gap: 8px;
  align-items: center;
  padding: 10px 12px;
}

.column-settings-head {
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 12px;
  color: #64748b;
}

.column-settings-head__show,
.column-settings-head__order {
  text-align: center;
}

.column-settings-row {
  border-bottom: 1px solid #f1f5f9;
}

.column-settings-row:last-child {
  border-bottom: none;
}

.column-settings-row--locked {
  background: #f8fafc;
}

.column-settings-row--hidden {
  opacity: 0.65;
}

.column-settings-check {
  justify-self: center;
  transform: scale(0.9);
}

.column-settings-name {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.column-settings-label {
  font-size: 14px;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.column-settings-tag {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 10px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 11px;
}

.column-settings-order {
  width: 56px;
  height: 32px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  text-align: center;
  font-size: 14px;
  color: #1677ff;
  background: #f0f7ff;
  box-sizing: border-box;
}

.dialog--tall {
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.column-scroll {
  flex: 1;
  min-height: 0;
  max-height: 50vh;
  margin-bottom: 8px;
}

.empty {
  text-align: center;
  color: #94a3b8;
  padding: 40px 0;
}

.mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  box-sizing: border-box;
}

.dialog {
  position: relative;
  z-index: 1001;
  width: 100%;
  max-width: 360px;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-sizing: border-box;
}

.dialog__title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  display: block;
}

.field {
  margin-bottom: 10px;
}

.field__label {
  display: block;
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
}

.field__req {
  color: #f56c6c;
  margin-right: 2px;
}

.input,
.textarea {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 0;
  font-size: 14px;
  box-sizing: border-box;
  background: #fff;
  color: #1e293b;
  pointer-events: auto;
}

.textarea {
  min-height: 80px;
}

.picker {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 10px;
  font-size: 14px;
}

.dialog__acts {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}

.btn {
  flex: 1;
  font-size: 14px;
}

.btn--primary {
  background: #1677ff;
  color: #fff;
}

.select-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1102;
  background: #fff;
  border-radius: 16px 16px 0 0;
  max-height: 52vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 -8px 24px rgba(15, 23, 42, 0.12);
}

.select-sheet__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.select-sheet__title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.status-pick {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 44px;
  padding: 0 12px;
  margin-bottom: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  box-sizing: border-box;
}

.status-pick__label {
  flex-shrink: 0;
  font-size: 14px;
  color: #64748b;
}

.status-pick__value {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  color: #1e293b;
  font-weight: 500;
  text-align: right;
}

.status-pick__arrow {
  flex-shrink: 0;
  font-size: 12px;
  color: #94a3b8;
}

.select-sheet__cancel {
  color: #64748b;
  font-size: 15px;
}

.select-sheet__ok {
  color: #1677ff;
  font-size: 15px;
  font-weight: 600;
}

.select-sheet__scroll {
  flex: 1;
  min-height: 0;
  max-height: calc(52vh - 48px);
}

.select-sheet__opt {
  padding: 14px 16px;
  font-size: 16px;
  color: #334155;
  border-bottom: 1px solid #f8fafc;
  text-align: center;
}

.select-sheet__opt--active {
  color: #1677ff;
  font-weight: 600;
  background: #f0f7ff;
}
</style>
