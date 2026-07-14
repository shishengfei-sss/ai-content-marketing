<script setup>
import { computed, onMounted, ref } from 'vue'
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
import OrderFormDialog from './OrderFormDialog.vue'

const router = useRouter()
const auth = useAuthStore()
const { fields, loadSchema } = useEntitySchema('order')
const { resolveMemberName, loadMembers, members } = useTeamMembers()

const statusFilter = ref('')
const formVisible = ref(false)
const editingRecord = ref(null)

const canCreate = () => hasPermission(auth.permissions, 'crm.order.create')
const canEdit = () => hasPermission(auth.permissions, 'crm.order.edit')
const canPlace = () => hasPermission(auth.permissions, 'crm.order.place')
const canDelete = () => hasPermission(auth.permissions, 'crm.order.delete')

const STATUS_META = {
  draft: { label: '草稿', type: 'info' },
  confirmed: { label: '已确认', type: 'success' },
  executing: { label: '执行中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  cancelled: { label: '已取消', type: 'danger' },
}
const SOURCE_META = { deal: '商机', quote: '报价', contract: '合同' }
function statusMeta(s) { return STATUS_META[s] || { label: s, type: '' } }

const {
  loading, items, total, page, pageSize, views, activeViewId, advancedFilters, advancedFilterVisible,
  searchKeyword, saveViewVisible, saveViewName, saveViewPinned, saveViewDefault, saveViewPublic,
  activeView, hasDraftFilters, hasTemporaryFilter, advancedFilterCount, defaultTableSort, tableSortKey,
  canSaveView, canManagePublic, loadViews, load, onSearch, onSearchClear, onViewChange,
  openAdvancedFilter, applyAdvancedFilters, openSaveView, submitSaveView, onViewsRefresh, clearActiveView,
  clearTemporaryFilters, onPageChange, initRouteView, watchRouteView,
} = useCrmViewList({
  entityType: 'order',
  listPath: '/crm/orders',
  fields,
  extraParams: computed(() => ({ status: statusFilter.value })),
  onResetExtra: () => { statusFilter.value = '' },
  fetcher: async (params) => {
    const { data } = await crmApi.listOrders(params)
    return { items: data.items || [], total: data.total || 0, filters_applied: data.filters_applied }
  },
})

function openCreate() { editingRecord.value = null; formVisible.value = true }
async function openEdit(row) { editingRecord.value = row; formVisible.value = true }
function goDetail(row) { router.push(`/crm/orders/${row.id}`) }

async function handleConfirm(row) {
  try { await crmApi.confirmOrder(row.id); ElMessage.success('已确认'); load() }
  catch (e) { ElMessage.error(e.message || '确认失败') }
}

async function handleCancel(row) {
  try {
    await ElMessageBox.confirm(`确定取消订单「${row.title}」？`, '取消订单')
    await crmApi.cancelOrder(row.id)
    ElMessage.success('已取消')
    load()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '取消失败') }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除订单「${row.title}」？`, '删除')
    await crmApi.deleteOrder(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

function formatAmount(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function formatDate(v) { return v ? String(v).replace('T', ' ').slice(0, 10) : '' }

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
      title="订单"
      :active-view="activeView"
      :filters-locked="!!activeViewId"
      :show-filter-hint="hasTemporaryFilter"
      @clear-view="clearActiveView"
      @clear-filters="clearTemporaryFilters"
    >
      <template #actions>
        <el-button v-if="canCreate()" type="primary" @click="openCreate">新建订单</el-button>
      </template>

      <template #view>
        <CrmViewSwitcher
          v-model="activeViewId"
          :views="views"
          all-label="全部订单"
          list-path="/crm/orders"
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
          placeholder="搜索订单号/标题"
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
        @row-click="goDetail"
      >
        <el-table-column prop="order_number" label="订单号" width="160" fixed="left" show-overflow-tooltip />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="来源" width="80" align="center">
          <template #default="{ row }">{{ SOURCE_META[row.source] || row.source }}</template>
        </el-table-column>
        <el-table-column label="金额" width="140" align="right">
          <template #default="{ row }">¥{{ formatAmount(row.amount) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }"><el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag></template>
        </el-table-column>
        <el-table-column label="下单日期" width="120">
          <template #default="{ row }">{{ formatDate(row.order_date) }}</template>
        </el-table-column>
        <el-table-column label="负责人" width="110" fixed="right">
          <template #default="{ row }">{{ resolveMemberName(row.owner_user_id) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right" align="center" @click.stop>
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
            <el-button v-if="canEdit() && row.status === 'draft'" link @click.stop="openEdit(row)">编辑</el-button>
            <el-button v-if="canPlace() && row.status === 'draft'" link type="success" @click.stop="handleConfirm(row)">确认</el-button>
            <el-button v-if="canEdit() && row.status !== 'cancelled' && row.status !== 'completed'" link type="warning" @click.stop="handleCancel(row)">取消</el-button>
            <el-button v-if="canDelete()" link type="danger" @click.stop="handleDelete(row)">删除</el-button>
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

    <OrderFormDialog v-model:visible="formVisible" :record="editingRecord" @saved="load" />
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
