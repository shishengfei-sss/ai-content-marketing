<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useEntitySchema } from '../../composables/useEntitySchema'
import { useCrmListColumns } from '../../composables/useCrmListColumns'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { useCrmViewList } from '../../composables/useCrmViewList'
import CrmListToolbar from '../../components/crm/CrmListToolbar.vue'
import CrmViewSwitcher from '../../components/crm/CrmViewSwitcher.vue'
import CrmAdvancedFilterDialog from '../../components/crm/CrmAdvancedFilterDialog.vue'
import CrmColumnSettingsDialog from '../../components/crm/CrmColumnSettingsDialog.vue'
import QuoteFormDialog from './QuoteFormDialog.vue'

const router = useRouter()
const auth = useAuthStore()
const { listColumns, fields, loadSchema, loadColumnSettingsDraft, saveListColumns, formatCell, applyListColumns } =
  useEntitySchema('quote')
const { leftFixedColumns, scrollColumns, rightFixedColumns } = useCrmListColumns(listColumns)
const { resolveMemberName, loadMembers, members } = useTeamMembers()

const statusFilter = ref('')
const ownerFilter = ref('')
const customerFilter = ref('')
const customerOptions = ref([])
const customerLoading = ref(false)
const formVisible = ref(false)
const editingRecord = ref(null)
const columnVisible = ref(false)
const columnDraft = ref([])
const customerNameMap = ref({})

const canCreate = () => hasPermission(auth.permissions, 'crm.quote.create')
const canEdit = () => hasPermission(auth.permissions, 'crm.quote.edit')
const canDelete = () => hasPermission(auth.permissions, 'crm.quote.delete')
const canSend = () => hasPermission(auth.permissions, 'crm.quote.send')
const canAccept = () => hasPermission(auth.permissions, 'crm.quote.accept')
const canConvert = () => hasPermission(auth.permissions, 'crm.order.convert')

function sameUserId(a, b) {
  if (!a || !b) return false
  return String(a).replace(/-/g, '').toLowerCase() === String(b).replace(/-/g, '').toLowerCase()
}
function isQuoteOwner(row) {
  return sameUserId(row?.owner_user_id, auth.user?.id)
}
function canEditRow(row) {
  return canEdit() && isQuoteOwner(row) && row?.status === 'draft'
}
function canSendRow(row) {
  return canSend() && isQuoteOwner(row) && row?.status === 'draft'
}
function canAcceptRow(row) {
  return canAccept() && isQuoteOwner(row) && row?.status === 'sent'
}
function canConvertRow(row) {
  return canConvert() && isQuoteOwner(row) && row?.status === 'accepted'
}
function canDeleteRow(row) {
  // 与撤回/拒绝互斥：已发送走撤回或拒绝；草稿/拒绝/过期可删
  return canDelete() && isQuoteOwner(row) && ['draft', 'rejected', 'expired'].includes(row?.status)
}

const STATUS_OPTIONS = [
  { value: 'draft', label: '草稿', type: 'info' },
  { value: 'sent', label: '已发送', type: 'warning' },
  { value: 'accepted', label: '已接受', type: 'success' },
  { value: 'rejected', label: '已拒绝', type: 'danger' },
  { value: 'expired', label: '已过期', type: 'info' },
  { value: 'ordered', label: '已转单', type: 'success' },
]
function statusMeta(s) {
  return STATUS_OPTIONS.find((x) => x.value === s) || { label: s, type: '' }
}

const ownerOptions = computed(() => (members.value || []).filter((m) => m.is_active !== false))

function onQuickFilterChange() {
  page.value = 1
  load()
}

function customerName(id) {
  if (!id) return '—'
  return customerNameMap.value[String(id)] || customerNameMap.value[String(id).replace(/-/g, '')] || String(id)
}

async function resolveCustomerNames(rows) {
  const ids = [...new Set((rows || []).map((r) => r.customer_id).filter(Boolean))]
  const missing = ids.filter((id) => !customerNameMap.value[String(id)] && !customerNameMap.value[String(id).replace(/-/g, '')])
  if (!missing.length) return
  await Promise.all(
    missing.map(async (id) => {
      try {
        const { data } = await crmApi.getCustomer(id)
        const name = data?.company_name || String(id)
        customerNameMap.value = {
          ...customerNameMap.value,
          [String(id)]: name,
          [String(id).replace(/-/g, '')]: name,
        }
      } catch {
        /* keep raw id */
      }
    }),
  )
}

async function searchCustomers(q = '') {
  customerLoading.value = true
  try {
    const { data } = await crmApi.listCustomers({ page: 1, page_size: 50, q })
    customerOptions.value = (data.items || []).map((c) => ({
      id: c.id,
      company_name: c.company_name,
    }))
  } catch {
    customerOptions.value = []
  } finally {
    customerLoading.value = false
  }
}

const {
  loading, items, total, page, pageSize, views, activeViewId, advancedFilters, advancedFilterVisible,
  searchKeyword, saveViewVisible, saveViewName, saveViewPinned, saveViewDefault, saveViewPublic,
  activeView, hasDraftFilters, hasTemporaryFilter, advancedFilterCount, defaultTableSort, tableSortKey,
  canSaveView, canManagePublic, loadViews, load, onSearch, onSearchClear, onSortChange, onViewChange,
  openAdvancedFilter, applyAdvancedFilters, openSaveView, submitSaveView, onViewsRefresh, clearActiveView,
  clearTemporaryFilters, onPageChange, initRouteView, watchRouteView,
} = useCrmViewList({
  entityType: 'quote',
  listPath: '/crm/quotes',
  fields,
  extraParams: computed(() => ({
    status: statusFilter.value,
    owner_id: ownerFilter.value || undefined,
    customer_id: customerFilter.value || undefined,
  })),
  onResetExtra: () => {
    statusFilter.value = ''
    ownerFilter.value = ''
    customerFilter.value = ''
  },
  getExtraDraftActive: () => !!(statusFilter.value || ownerFilter.value || customerFilter.value),
  collectExtraFilterConditions: () => {
    const conditions = []
    if (statusFilter.value) conditions.push({ field_key: 'status', op: 'eq', value: statusFilter.value })
    if (ownerFilter.value) conditions.push({ field_key: 'owner_user_id', op: 'eq', value: ownerFilter.value })
    if (customerFilter.value) conditions.push({ field_key: 'customer_id', op: 'eq', value: customerFilter.value })
    return conditions
  },
  suggestExtraViewNameBits: () => {
    const bits = []
    if (statusFilter.value) {
      const st = STATUS_OPTIONS.find((o) => o.value === statusFilter.value)
      if (st) bits.push(st.label)
    }
    if (ownerFilter.value) {
      const m = ownerOptions.value.find((x) => String(x.user_id) === String(ownerFilter.value))
      if (m) bits.push(m.display_name || m.phone || '负责人')
    }
    if (customerFilter.value) {
      const c = customerOptions.value.find((x) => String(x.id) === String(customerFilter.value))
      if (c) bits.push(c.company_name)
    }
    return bits
  },
  fetcher: async (params) => {
    const { data } = await crmApi.listQuotes(params)
    if (data.list_fields?.length) applyListColumns(data.list_fields)
    await resolveCustomerNames(data.items || [])
    return { items: data.items || [], total: data.total || 0, filters_applied: data.filters_applied }
  },
})

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
    load()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}

function openCreate() { editingRecord.value = null; formVisible.value = true }
function openEdit(row) { editingRecord.value = row; formVisible.value = true }
function goDetail(row) { router.push(`/crm/quotes/${row.id}`) }

async function handleSend(row) {
  try { await crmApi.sendQuote(row.id); ElMessage.success('已发送'); load() }
  catch (e) { ElMessage.error(e.message || '发送失败') }
}

async function handleAccept(row) {
  try { await crmApi.acceptQuote(row.id); ElMessage.success('已标记接受'); load() }
  catch (e) { ElMessage.error(e.message || '操作失败') }
}

async function handleConvert(row) {
  try {
    await ElMessageBox.confirm(`将报价「${row.subject}」转化为订单？`, '转化为订单')
    const { data } = await crmApi.convertQuoteToOrder(row.id)
    ElMessage.success('已转化为订单')
    router.push(`/crm/orders/${data.order_id}`)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '转化失败')
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除报价「${row.subject}」？`, '删除')
    await crmApi.deleteQuote(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const SORTABLE_KEYS = new Set(['quote_number', 'subject', 'total_amount', 'status', 'valid_until'])

function cellText(row, col) {
  if (col.field_key === 'status') return statusMeta(row.status).label
  if (col.field_key === 'customer_id') return customerName(row.customer_id)
  if (col.field_key === 'owner_user_id' || col.field_key === 'created_by_user_id') {
    return resolveMemberName(row[col.field_key])
  }
  if (col.field_type === 'currency' || col.field_key === 'total_amount') {
    const v = row[col.field_key]
    if (v === undefined || v === null || v === '') return '—'
    return `¥${formatAmount(v)}`
  }
  return formatCell(row, col.field_key, col.field_type)
}

let stopRouteWatch = null
onMounted(async () => {
  initRouteView()
  await Promise.all([loadSchema(), loadMembers(), searchCustomers('')])
  await loadViews()
  load()
  stopRouteWatch = watchRouteView()
})
</script>

<template>
  <div class="page-card">
    <CrmListToolbar
      title="报价"
      :active-view="activeView"
      :filters-locked="!!activeViewId"
      :show-filter-hint="hasTemporaryFilter"
      @clear-view="clearActiveView"
      @clear-filters="clearTemporaryFilters"
    >
      <template #actions>
        <el-button @click="openColumnSettings">列设置</el-button>
        <el-button v-if="canCreate()" type="primary" @click="openCreate">新建报价</el-button>
        <el-button v-if="canCreate()" @click="router.push('/crm/quotes/cpq/new')">CPQ 配置报价</el-button>
      </template>

      <template #view>
        <CrmViewSwitcher
          v-model="activeViewId"
          :views="views"
          all-label="全部报价"
          list-path="/crm/quotes"
          :can-save="canSaveView()"
          :has-draft-filters="hasDraftFilters"
          @change="onViewChange"
          @save="openSaveView"
          @refresh="onViewsRefresh"
        />
      </template>

      <template #filters>
        <el-select
          v-model="statusFilter"
          clearable
          placeholder="状态"
          class="crm-list-filter-select"
          :disabled="!!activeViewId"
          @change="onQuickFilterChange"
        >
          <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select
          v-model="ownerFilter"
          clearable
          filterable
          placeholder="负责人"
          class="crm-list-filter-select crm-list-filter-select--wide"
          :disabled="!!activeViewId"
          @change="onQuickFilterChange"
        >
          <el-option
            v-for="m in ownerOptions"
            :key="m.user_id"
            :label="m.display_name || m.phone || m.user_id"
            :value="m.user_id"
          />
        </el-select>
        <el-select
          v-model="customerFilter"
          clearable
          filterable
          remote
          :remote-method="searchCustomers"
          :loading="customerLoading"
          placeholder="客户"
          class="crm-list-filter-select crm-list-filter-select--wide"
          :disabled="!!activeViewId"
          @change="onQuickFilterChange"
          @focus="() => { if (!customerOptions.length) searchCustomers('') }"
        >
          <el-option
            v-for="c in customerOptions"
            :key="c.id"
            :label="c.company_name"
            :value="c.id"
          />
        </el-select>
        <el-input
          v-model="searchKeyword"
          class="crm-list-search"
          placeholder="搜索报价单号/主题"
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

    <CrmColumnSettingsDialog
      v-model:visible="columnVisible"
      v-model:columns="columnDraft"
      @save="submitColumnSettings"
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
          :sortable="SORTABLE_KEYS.has(col.field_key) ? 'custom' : false"
          show-overflow-tooltip
        >
          <template #default="{ row }">{{ cellText(row, col) }}</template>
        </el-table-column>
        <el-table-column
          v-for="col in scrollColumns"
          :key="col.field_key"
          :prop="col.field_key"
          :label="col.label"
          :min-width="col.width || 120"
          :sortable="SORTABLE_KEYS.has(col.field_key) ? 'custom' : false"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <el-tag v-if="col.field_key === 'status'" :type="statusMeta(row.status).type" size="small">
              {{ statusMeta(row.status).label }}
            </el-tag>
            <template v-else>{{ cellText(row, col) }}</template>
          </template>
        </el-table-column>
        <el-table-column
          v-for="col in rightFixedColumns"
          :key="col.field_key"
          :prop="col.field_key"
          :label="col.label"
          fixed="right"
          :width="col.width || 110"
          show-overflow-tooltip
        >
          <template #default="{ row }">{{ resolveMemberName(row.owner_user_id) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right" align="center" @click.stop>
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
            <el-button v-if="canEditRow(row)" link @click.stop="openEdit(row)">编辑</el-button>
            <el-button v-if="canSendRow(row)" link type="warning" @click.stop="handleSend(row)">发送</el-button>
            <el-button v-if="canAcceptRow(row)" link type="success" @click.stop="handleAccept(row)">接受</el-button>
            <el-button v-if="canConvertRow(row)" link type="primary" @click.stop="handleConvert(row)">转订单</el-button>
            <el-button v-if="canDeleteRow(row)" link type="danger" @click.stop="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pager">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="onPageChange" />
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

    <QuoteFormDialog v-model:visible="formVisible" :record="editingRecord" @saved="load" />
  </div>
</template>

<style scoped>
.crm-adv-filter-btn { position: relative; }
.crm-adv-filter-badge { margin-left: 4px; }
.crm-adv-filter-badge :deep(.el-badge__content) {
  position: static;
  transform: none;
  vertical-align: middle;
}
.crm-list-filter-select { width: 120px; }
.crm-list-filter-select--wide { width: 160px; }
</style>
