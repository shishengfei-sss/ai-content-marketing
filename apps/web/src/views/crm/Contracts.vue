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
import { CONTRACT_STATUS_META, CONTRACT_TYPE_META, contractActions } from '../../composables/contractActions'
import CrmListToolbar from '../../components/crm/CrmListToolbar.vue'
import CrmViewSwitcher from '../../components/crm/CrmViewSwitcher.vue'
import CrmAdvancedFilterDialog from '../../components/crm/CrmAdvancedFilterDialog.vue'
import CrmColumnSettingsDialog from '../../components/crm/CrmColumnSettingsDialog.vue'
import ContractFormDialog from './ContractFormDialog.vue'

const router = useRouter()
const auth = useAuthStore()
const { listColumns, fields, loadSchema, loadColumnSettingsDraft, saveListColumns, formatCell, applyListColumns } =
  useEntitySchema('contract')
const { leftFixedColumns, scrollColumns, rightFixedColumns } = useCrmListColumns(listColumns)
const { resolveMemberName, loadMembers, members } = useTeamMembers()

const statusFilter = ref('')
const formVisible = ref(false)
const editingRecord = ref(null)
const columnVisible = ref(false)
const columnDraft = ref([])
const customerNameMap = ref({})
const selectedIds = ref([])
const batchActing = ref(false)
const exporting = ref(false)

const signVisible = ref(false)
const signForm = ref({ signed_amount: null, signed_at: '' })
const signingId = ref('')

const canCreate = () => hasPermission(auth.permissions, 'crm.contract.create')
const canEdit = () => hasPermission(auth.permissions, 'crm.contract.edit')
const canSign = () => hasPermission(auth.permissions, 'crm.contract.sign')
const canDelete = () => hasPermission(auth.permissions, 'crm.contract.delete')
const canConvert = () => hasPermission(auth.permissions, 'crm.order.convert')

function sameUserId(a, b) {
  if (!a || !b) return false
  return String(a).replace(/-/g, '').toLowerCase() === String(b).replace(/-/g, '').toLowerCase()
}
function isOwner(row) {
  return sameUserId(row?.owner_user_id, auth.user?.id)
}
function rowActions(row) {
  return contractActions({
    status: row?.status,
    isOwner: isOwner(row),
    canEdit: canEdit(),
    canSign: canSign(),
    canCreate: canCreate(),
    canDelete: canDelete(),
    canConvert: canConvert(),
  })
}

const STATUS_META = CONTRACT_STATUS_META
const TYPE_META = CONTRACT_TYPE_META
function statusMeta(s) { return STATUS_META[s] || { label: s, type: '' } }

function onSelectionChange(rows) {
  selectedIds.value = (rows || []).map((r) => r.id)
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

const {
  loading, items, total, page, pageSize, views, activeViewId, advancedFilters, advancedFilterVisible,
  searchKeyword, saveViewVisible, saveViewName, saveViewPinned, saveViewDefault, saveViewPublic,
  activeView, hasDraftFilters, hasTemporaryFilter, advancedFilterCount, defaultTableSort, tableSortKey,
  canSaveView, canManagePublic, loadViews, load, onSearch, onSearchClear, onViewChange,
  openAdvancedFilter, applyAdvancedFilters, openSaveView, submitSaveView, onViewsRefresh, clearActiveView,
  clearTemporaryFilters, onPageChange, initRouteView, watchRouteView,
} = useCrmViewList({
  entityType: 'contract',
  listPath: '/crm/contracts',
  fields,
  extraParams: computed(() => ({ status: statusFilter.value })),
  onResetExtra: () => { statusFilter.value = '' },
  fetcher: async (params) => {
    const { data } = await crmApi.listContracts(params)
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

function openCreate() {
  editingRecord.value = null
  formVisible.value = true
}

function openEdit(row) {
  editingRecord.value = row
  formVisible.value = true
}

function openSign(row) {
  signingId.value = row.id
  signForm.value = { signed_amount: Number(row.amount), signed_at: '' }
  signVisible.value = true
}

async function submitSign() {
  try {
    await crmApi.signContract(signingId.value, {
      signed_amount: signForm.value.signed_amount,
      signed_at: signForm.value.signed_at || null,
    })
    ElMessage.success('已签署')
    signVisible.value = false
    load()
  } catch (e) { ElMessage.error(e.message || '签署失败') }
}

async function handleSend(row) {
  try {
    await crmApi.sendContract(row.id)
    ElMessage.success('已发送')
    load()
  } catch (e) { ElMessage.error(e.message || '发送失败') }
}

async function handleConvert(row) {
  try {
    await ElMessageBox.confirm(`将合同「${row.title}」生成订单？（合同可重复生成订单）`, '生成订单')
    const { data } = await crmApi.convertContractToOrder(row.id)
    ElMessage.success('已生成订单')
    router.push(`/crm/orders/${data.order_id}`)
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '转化失败') }
}

async function handleClone(row) {
  try {
    const { data } = await crmApi.cloneContract(row.id)
    ElMessage.success('已复制')
    router.push(`/crm/contracts/${data.id}`)
  } catch (e) { ElMessage.error(e.message || '复制失败') }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除合同「${row.title}」？`, '删除')
    await crmApi.deleteContract(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

async function handleBatch(action) {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选合同')
    return
  }
  const label = action === 'sign' ? '签署' : '发送'
  try {
    await ElMessageBox.confirm(`对已选 ${selectedIds.value.length} 条合同执行「批量${label}」？失败项将跳过。`, `批量${label}`)
  } catch {
    return
  }
  batchActing.value = true
  try {
    const { data } = await crmApi.batchContractAction({
      contract_ids: selectedIds.value,
      action,
    })
    ElMessage.success(`成功 ${data.succeeded}，失败 ${data.failed}`)
    selectedIds.value = []
    load()
  } catch (e) {
    ElMessage.error(e.message || '批量操作失败')
  } finally {
    batchActing.value = false
  }
}

async function handleExport(format) {
  exporting.value = true
  try {
    const params = {
      format,
      q: searchKeyword.value || undefined,
      status: statusFilter.value || undefined,
      view_id: activeViewId.value || undefined,
    }
    if (!activeViewId.value && advancedFilters.value?.conditions?.length) {
      params.filters = JSON.stringify(advancedFilters.value)
    }
    const { data, headers } = await crmApi.exportContracts(params)
    const blob = data instanceof Blob ? data : new Blob([data])
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = format === 'xlsx' ? 'contracts.xlsx' : 'contracts.csv'
    a.click()
    URL.revokeObjectURL(url)
    const rowCount = headers?.['x-export-row-count'] || headers?.['X-Export-Row-Count']
    ElMessage.success(rowCount ? `已导出 ${rowCount} 条` : '已导出')
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

function goDetail(row) { router.push(`/crm/contracts/${row.id}`) }
function formatAmount(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

function cellText(row, col) {
  if (col.field_key === 'status') return statusMeta(row.status).label
  if (col.field_key === 'contract_type') return TYPE_META[row.contract_type] || row.contract_type || '—'
  if (col.field_key === 'customer_id') return customerName(row.customer_id)
  if (col.field_key === 'owner_user_id' || col.field_key === 'created_by_user_id') {
    return resolveMemberName(row[col.field_key])
  }
  if (col.field_key === 'amount') {
    const v = row.signed_amount != null ? row.signed_amount : row.amount
    if (v === undefined || v === null || v === '') return '—'
    return `¥${formatAmount(v)}`
  }
  if (col.field_type === 'currency' || col.field_key === 'signed_amount') {
    const v = row[col.field_key]
    if (v === undefined || v === null || v === '') return '—'
    return `¥${formatAmount(v)}`
  }
  return formatCell(row, col.field_key, col.field_type)
}

onMounted(async () => {
  initRouteView()
  await Promise.all([loadSchema(), loadMembers()])
  await loadViews()
  load()
  watchRouteView()
})
</script>

<template>
  <div class="page-card">
    <CrmListToolbar
      title="合同"
      :active-view="activeView"
      :filters-locked="!!activeViewId"
      :show-filter-hint="hasTemporaryFilter"
      @clear-view="clearActiveView"
      @clear-filters="clearTemporaryFilters"
    >
      <template #actions>
        <el-button
          v-if="canSign()"
          :disabled="!selectedIds.length"
          :loading="batchActing"
          @click="handleBatch('sign')"
        >批量签署</el-button>
        <el-button
          v-if="canEdit()"
          :disabled="!selectedIds.length"
          :loading="batchActing"
          @click="handleBatch('send')"
        >批量发送</el-button>
        <el-dropdown :disabled="exporting" @command="handleExport">
          <el-button :loading="exporting">导出</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="csv">导出 CSV</el-dropdown-item>
              <el-dropdown-item command="xlsx">导出 Excel</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="openColumnSettings">列设置</el-button>
        <el-button v-if="canCreate()" type="primary" @click="openCreate">新建合同</el-button>
      </template>

      <template #view>
        <CrmViewSwitcher
          v-model="activeViewId"
          :views="views"
          all-label="全部合同"
          list-path="/crm/contracts"
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
          class="crm-list-status-filter"
          :disabled="!!activeViewId"
          @change="() => { page = 1; load() }"
        >
          <el-option v-for="(m, k) in STATUS_META" :key="k" :label="m.label" :value="k" />
        </el-select>
        <el-input
          v-model="searchKeyword"
          class="crm-list-search"
          placeholder="搜索合同号/标题"
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
        @selection-change="onSelectionChange"
        @row-click="goDetail"
      >
        <el-table-column type="selection" width="48" fixed="left" @click.stop />
        <el-table-column
          v-for="col in leftFixedColumns"
          :key="col.field_key"
          :prop="col.field_key"
          :label="col.label"
          fixed="left"
          :min-width="col.width || 160"
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
        <el-table-column label="操作" width="300" fixed="right" align="center" @click.stop>
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
            <el-button v-if="rowActions(row).edit" link @click.stop="openEdit(row)">编辑</el-button>
            <el-button v-if="rowActions(row).send" link @click.stop="handleSend(row)">发送</el-button>
            <el-button v-if="rowActions(row).sign" link type="success" @click.stop="openSign(row)">签署</el-button>
            <el-button v-if="rowActions(row).convert" link type="primary" @click.stop="handleConvert(row)">生成订单</el-button>
            <el-button v-if="rowActions(row).clone" link @click.stop="handleClone(row)">复制</el-button>
            <el-button v-if="rowActions(row).delete" link type="danger" @click.stop="handleDelete(row)">删除</el-button>
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

    <ContractFormDialog v-model:visible="formVisible" :record="editingRecord" @saved="load" />

    <el-dialog v-model="signVisible" title="签署合同" width="420px">
      <el-form label-width="88px">
        <el-form-item label="签署金额">
          <el-input-number v-model="signForm.signed_amount" :min="0" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="签署日期">
          <el-date-picker v-model="signForm.signed_at" type="date" value-format="YYYY-MM-DD" style="width: 200px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="signVisible = false">取消</el-button>
        <el-button type="primary" @click="submitSign">确认签署</el-button>
      </template>
    </el-dialog>
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
.crm-list-status-filter { width: 120px; }
</style>
