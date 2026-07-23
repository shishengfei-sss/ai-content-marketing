<script setup>
import { computed, onMounted, ref, watch } from 'vue'
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

const router = useRouter()
const auth = useAuthStore()
const { listColumns, fields, loadSchema, loadColumnSettingsDraft, saveListColumns, formatCell, applyListColumns } =
  useEntitySchema('payment')
const { leftFixedColumns, scrollColumns, rightFixedColumns } = useCrmListColumns(listColumns)
const { resolveMemberName, loadMembers, members } = useTeamMembers()

const statusFilter = ref('')
const columnVisible = ref(false)
const columnDraft = ref([])
const orderLabelMap = ref({})
const customerNameMap = ref({})

const dialogVisible = ref(false)
const saving = ref(false)
const orderOptions = ref([])
const orderLoading = ref(false)
const form = ref(emptyForm())

function emptyForm() { return { order_id: '', amount: null, paid_at: '', method: 'bank', status: 'pending', remark: '' } }

const canCreate = () => hasPermission(auth.permissions, 'crm.payment.create')
const canConfirm = () => hasPermission(auth.permissions, 'crm.payment.confirm')
const canReverse = () => hasPermission(auth.permissions, 'crm.payment.reverse')
const canDelete = () => hasPermission(auth.permissions, 'crm.payment.delete')

function sameUserId(a, b) {
  if (!a || !b) return false
  return String(a).replace(/-/g, '').toLowerCase() === String(b).replace(/-/g, '').toLowerCase()
}
function isOwner(row) {
  return sameUserId(row?.owner_user_id, auth.user?.id)
}
function canConfirmRow(row) {
  return canConfirm() && isOwner(row) && row?.status === 'pending'
}
function canReverseRow(row) {
  return canReverse() && isOwner(row) && row?.status === 'confirmed'
}
function canDeleteRow(row) {
  return canDelete() && isOwner(row) && row?.status === 'pending'
}

const STATUS_META = { pending: { label: '待确认', type: 'warning' }, confirmed: { label: '已到账', type: 'success' }, reversed: { label: '已冲销', type: 'info' } }
const METHOD_META = { bank: '银行', wechat: '微信', alipay: '支付宝', cash: '现金', other: '其他' }
function statusMeta(s) { return STATUS_META[s] || { label: s, type: '' } }

function orderLabel(id) {
  if (!id) return '—'
  return orderLabelMap.value[String(id)] || orderLabelMap.value[String(id).replace(/-/g, '')] || String(id)
}

function customerName(id) {
  if (!id) return '—'
  return customerNameMap.value[String(id)] || customerNameMap.value[String(id).replace(/-/g, '')] || String(id)
}

async function resolveOrderLabels(rows) {
  const ids = [...new Set((rows || []).map((r) => r.order_id).filter(Boolean))]
  const missing = ids.filter((id) => !orderLabelMap.value[String(id)] && !orderLabelMap.value[String(id).replace(/-/g, '')])
  if (!missing.length) return
  await Promise.all(
    missing.map(async (id) => {
      try {
        const { data } = await crmApi.getOrder(id)
        const label = data?.order_number
          ? `${data.order_number}${data.title ? ` · ${data.title}` : ''}`
          : String(id)
        orderLabelMap.value = {
          ...orderLabelMap.value,
          [String(id)]: label,
          [String(id).replace(/-/g, '')]: label,
        }
      } catch {
        /* keep raw id */
      }
    }),
  )
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
  entityType: 'payment',
  listPath: '/crm/payments',
  fields,
  extraParams: computed(() => ({ status: statusFilter.value })),
  onResetExtra: () => { statusFilter.value = '' },
  fetcher: async (params) => {
    const { data } = await crmApi.listPayments(params)
    if (data.list_fields?.length) applyListColumns(data.list_fields)
    await Promise.all([
      resolveOrderLabels(data.items || []),
      resolveCustomerNames(data.items || []),
    ])
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

async function searchOrders(q = '') {
  orderLoading.value = true
  try {
    const { data } = await crmApi.listOrders({
      page: 1,
      page_size: 50,
      q,
      // BR-PAY-01：仅已确认/执行中/已完成可登记回款
      filters: JSON.stringify({
        logic: 'and',
        conditions: [{ field_key: 'status', op: 'in', value: ['confirmed', 'executing', 'completed'] }],
      }),
    })
    orderOptions.value = (data.items || [])
      .filter((o) => ['confirmed', 'executing', 'completed'].includes(o.status))
      .map((o) => ({
        id: o.id,
        title: o.title,
        order_number: o.order_number,
        amount: Number(o.amount || 0),
      }))
  } catch { orderOptions.value = [] } finally { orderLoading.value = false }
}

/** 未回款 = 订单金额 − 已确认回款，与订单详情口径一致 */
async function fillUnpaidAmount(orderId) {
  if (!orderId) {
    form.value.amount = null
    return
  }
  const cached = orderOptions.value.find((o) => o.id === orderId)
  // 先用列表缓存金额即时带出，再按已确认回款精算
  if (cached && Number(cached.amount) > 0) {
    form.value.amount = Math.round(Number(cached.amount) * 100) / 100
  }
  try {
    const [orderRes, payRes] = await Promise.all([
      crmApi.getOrder(orderId),
      // page_size 上限 100，超过会 422 导致金额无法带出
      crmApi.listPayments({ order_id: orderId, page: 1, page_size: 100 }),
    ])
    const orderAmount = Number(orderRes.data?.amount ?? cached?.amount ?? 0)
    const paidTotal = (payRes.data?.items || [])
      .filter((p) => p.status === 'confirmed')
      .reduce((acc, p) => acc + Number(p.amount || 0), 0)
    const unpaid = Math.max(0, Math.round((orderAmount - paidTotal) * 100) / 100)
    form.value.amount = unpaid > 0 ? unpaid : null
  } catch {
    // 精算失败时保留缓存金额（若有），不打断选单
    if (form.value.amount == null && cached) {
      const fallback = Math.round(Number(cached.amount || 0) * 100) / 100
      form.value.amount = fallback > 0 ? fallback : null
    }
  }
}

function openCreate() {
  form.value = emptyForm()
  dialogVisible.value = true
}

async function submit() {
  if (!form.value.order_id) { ElMessage.warning('请选择订单'); return }
  if (form.value.amount == null) { ElMessage.warning('请填写回款金额'); return }
  saving.value = true
  try {
    await crmApi.createPayment({
      order_id: form.value.order_id,
      amount: form.value.amount,
      paid_at: form.value.paid_at || null,
      method: form.value.method,
      status: form.value.status,
      remark: form.value.remark || null,
    })
    ElMessage.success('回款已登记')
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message || '登记失败')
  } finally {
    saving.value = false
  }
}

async function handleConfirm(row) {
  try { await crmApi.confirmPayment(row.id); ElMessage.success('已确认到账'); load() }
  catch (e) { ElMessage.error(e.message || '确认失败') }
}

async function handleReverse(row) {
  try {
    await ElMessageBox.confirm('确定冲销该回款？', '冲销')
    await crmApi.reversePayment(row.id)
    ElMessage.success('已冲销')
    load()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '冲销失败') }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除该回款记录？', '删除')
    await crmApi.deletePayment(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

const pageSummary = computed(() => {
  const rows = items.value || []
  // 按 order_id 去重后汇总计划/已回/逾期
  const byOrder = new Map()
  for (const row of rows) {
    if (!row.order_id || byOrder.has(row.order_id)) continue
    byOrder.set(row.order_id, {
      plan: Number(row.order_plan_total || 0),
      paid: Number(row.order_paid_total || 0),
      overdue: Number(row.order_overdue_amount || 0),
    })
  }
  let plan = 0, paid = 0, overdue = 0
  for (const v of byOrder.values()) {
    plan += v.plan
    paid += v.paid
    overdue += v.overdue
  }
  const pageAmount = rows.reduce((acc, r) => acc + Number(r.amount || 0), 0)
  const pageConfirmed = rows.filter((r) => r.status === 'confirmed').reduce((acc, r) => acc + Number(r.amount || 0), 0)
  return { plan, paid, overdue, pageAmount, pageConfirmed, orderCount: byOrder.size }
})

function goOrder(row) { router.push(`/crm/orders/${row.order_id}`) }
function goCustomer(row) {
  if (row.customer_id) router.push(`/crm/customers/${row.customer_id}`)
}
function goDetail(row) { router.push(`/crm/payments/${row.id}`) }
function formatAmount(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

const CURRENCY_KEYS = new Set(['amount', 'order_plan_total', 'order_paid_total', 'order_overdue_amount'])

function cellText(row, col) {
  if (col.field_key === 'status') return statusMeta(row.status).label
  if (col.field_key === 'method') return METHOD_META[row.method] || row.method || '—'
  if (col.field_key === 'order_id') return orderLabel(row.order_id)
  if (col.field_key === 'customer_id') return customerName(row.customer_id)
  if (col.field_key === 'owner_user_id' || col.field_key === 'created_by_user_id') {
    return resolveMemberName(row[col.field_key])
  }
  if (CURRENCY_KEYS.has(col.field_key) || col.field_type === 'currency') {
    const v = row[col.field_key]
    if (v === undefined || v === null || v === '') return '—'
    return `¥${formatAmount(v)}`
  }
  return formatCell(row, col.field_key, col.field_type)
}

watch(dialogVisible, async (v) => { if (v) await searchOrders('') })
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
      title="回款"
      :active-view="activeView"
      :filters-locked="!!activeViewId"
      :show-filter-hint="hasTemporaryFilter"
      @clear-view="clearActiveView"
      @clear-filters="clearTemporaryFilters"
    >
      <template #actions>
        <el-button @click="openColumnSettings">列设置</el-button>
        <el-button v-if="canCreate()" type="primary" @click="openCreate">登记回款</el-button>
      </template>

      <template #view>
        <CrmViewSwitcher
          v-model="activeViewId"
          :views="views"
          all-label="全部回款"
          list-path="/crm/payments"
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
          placeholder="搜索回款号"
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

    <div class="pay-summary">
      <div class="pay-summary__item">
        <span class="pay-summary__label">本页回款</span>
        <strong>¥{{ formatAmount(pageSummary.pageAmount) }}</strong>
        <em>已确认 ¥{{ formatAmount(pageSummary.pageConfirmed) }}</em>
      </div>
      <div class="pay-summary__item">
        <span class="pay-summary__label">关联订单计划（去重）</span>
        <strong>¥{{ formatAmount(pageSummary.plan) }}</strong>
        <em>{{ pageSummary.orderCount }} 单</em>
      </div>
      <div class="pay-summary__item">
        <span class="pay-summary__label">已回合计</span>
        <strong class="is-ok">¥{{ formatAmount(pageSummary.paid) }}</strong>
      </div>
      <div class="pay-summary__item">
        <span class="pay-summary__label">逾期</span>
        <strong class="is-warn">¥{{ formatAmount(pageSummary.overdue) }}</strong>
      </div>
    </div>

    <div class="crm-list-table-wrap">
      <el-table
        :key="tableSortKey"
        v-loading="loading"
        :data="items"
        border
        class="crm-list-table"
        :default-sort="defaultTableSort"
        :header-cell-class-name="() => 'crm-list-table__header-cell'"
      >
        <el-table-column
          v-for="col in leftFixedColumns"
          :key="col.field_key"
          :prop="col.field_key"
          :label="col.label"
          fixed="left"
          :min-width="col.width || 160"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <el-link v-if="col.field_key === 'payment_number'" type="primary" @click="goDetail(row)">
              {{ row.payment_number }}
            </el-link>
            <template v-else>{{ cellText(row, col) }}</template>
          </template>
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
            <el-link v-else-if="col.field_key === 'order_id'" type="primary" @click="goOrder(row)">
              {{ orderLabel(row.order_id) }}
            </el-link>
            <el-link
              v-else-if="col.field_key === 'customer_id' && row.customer_id"
              type="primary"
              @click="goCustomer(row)"
            >
              {{ customerName(row.customer_id) }}
            </el-link>
            <span
              v-else-if="col.field_key === 'order_overdue_amount'"
              :class="{ 'is-overdue': Number(row.order_overdue_amount || 0) > 0 }"
            >
              {{ cellText(row, col) }}
            </span>
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
        <el-table-column label="操作" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="goDetail(row)">详情</el-button>
            <el-button v-if="canConfirmRow(row)" link type="success" @click="handleConfirm(row)">确认</el-button>
            <el-button v-if="canReverseRow(row)" link type="warning" @click="handleReverse(row)">冲销</el-button>
            <el-button v-if="canDeleteRow(row)" link type="danger" @click="handleDelete(row)">删除</el-button>
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

    <el-dialog v-model="dialogVisible" title="登记回款" width="480px">
      <el-form label-width="88px">
        <el-form-item label="订单" required>
          <el-select
            v-model="form.order_id"
            filterable
            remote
            :remote-method="searchOrders"
            :loading="orderLoading"
            placeholder="搜索订单"
            style="width: 100%"
            @change="fillUnpaidAmount"
          >
            <el-option v-for="o in orderOptions" :key="o.id" :label="`${o.order_number} - ${o.title}`" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="回款金额"><el-input-number v-model="form.amount" :min="0" :precision="2" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="到账日期"><el-date-picker v-model="form.paid_at" type="date" value-format="YYYY-MM-DD" style="width: 200px" /></el-form-item>
        <el-form-item label="收款方式">
          <el-select v-model="form.method">
            <el-option label="银行" value="bank" />
            <el-option label="微信" value="wechat" />
            <el-option label="支付宝" value="alipay" />
            <el-option label="现金" value="cash" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="待确认" value="pending" />
            <el-option label="已到账" value="confirmed" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" maxlength="500" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
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
.pay-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 0 0 12px;
}
.pay-summary__item {
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}
.pay-summary__label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}
.pay-summary__item strong { font-size: 16px; }
.pay-summary__item em {
  display: block;
  margin-top: 2px;
  font-style: normal;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.pay-summary__item .is-ok { color: var(--el-color-success); }
.pay-summary__item .is-warn { color: var(--el-color-warning); }
.is-overdue { color: var(--el-color-danger); font-weight: 600; }
@media (max-width: 960px) {
  .pay-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
