<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useEntitySchema } from '../../composables/useEntitySchema'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { useCrmViewList } from '../../composables/useCrmViewList'
import CrmListToolbar from '../../components/crm/CrmListToolbar.vue'
import CrmViewSwitcher from '../../components/crm/CrmViewSwitcher.vue'
import CrmAdvancedFilterDialog from '../../components/crm/CrmAdvancedFilterDialog.vue'

const router = useRouter()
const auth = useAuthStore()
const { fields, loadSchema } = useEntitySchema('payment')
const { resolveMemberName, loadMembers, members } = useTeamMembers()

const statusFilter = ref('')

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

const STATUS_META = { pending: { label: '待确认', type: 'warning' }, confirmed: { label: '已到账', type: 'success' }, reversed: { label: '已冲销', type: 'info' } }
const METHOD_META = { bank: '银行', wechat: '微信', alipay: '支付宝', cash: '现金', other: '其他' }
function statusMeta(s) { return STATUS_META[s] || { label: s, type: '' } }

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
    return { items: data.items || [], total: data.total || 0, filters_applied: data.filters_applied }
  },
})

async function searchOrders(q = '') {
  orderLoading.value = true
  try {
    const { data } = await crmApi.listOrders({ page: 1, page_size: 50, q })
    orderOptions.value = (data.items || []).map((o) => ({ id: o.id, title: o.title, order_number: o.order_number }))
  } catch { orderOptions.value = [] } finally { orderLoading.value = false }
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

function goOrder(row) { router.push(`/crm/orders/${row.order_id}`) }
function formatAmount(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function formatDate(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '' }

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
        <el-table-column prop="payment_number" label="回款号" width="160" fixed="left" show-overflow-tooltip />
        <el-table-column label="订单" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" @click="goOrder(row)">{{ row.order_id }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="140" align="right">
          <template #default="{ row }">¥{{ formatAmount(row.amount) }}</template>
        </el-table-column>
        <el-table-column label="到账日" width="150">
          <template #default="{ row }">{{ formatDate(row.paid_at) }}</template>
        </el-table-column>
        <el-table-column label="方式" width="80" align="center">
          <template #default="{ row }">{{ METHOD_META[row.method] || row.method }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }"><el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag></template>
        </el-table-column>
        <el-table-column label="负责人" width="110" fixed="right">
          <template #default="{ row }">{{ resolveMemberName(row.owner_user_id) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button v-if="canConfirm() && row.status === 'pending'" link type="success" @click="handleConfirm(row)">确认</el-button>
            <el-button v-if="canReverse() && row.status === 'confirmed'" link type="warning" @click="handleReverse(row)">冲销</el-button>
            <el-button v-if="canDelete()" link type="danger" @click="handleDelete(row)">删除</el-button>
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
          <el-select v-model="form.order_id" filterable remote :remote-method="searchOrders" :loading="orderLoading" placeholder="搜索订单" style="width: 100%">
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
</style>
