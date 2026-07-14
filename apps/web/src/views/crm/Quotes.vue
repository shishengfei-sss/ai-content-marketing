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
import QuoteFormDialog from './QuoteFormDialog.vue'

const router = useRouter()
const auth = useAuthStore()
const { fields, loadSchema } = useEntitySchema('quote')
const { resolveMemberName, loadMembers, members } = useTeamMembers()

const statusFilter = ref('')
const formVisible = ref(false)
const editingRecord = ref(null)

const canCreate = () => hasPermission(auth.permissions, 'crm.quote.create')
const canEdit = () => hasPermission(auth.permissions, 'crm.quote.edit')
const canDelete = () => hasPermission(auth.permissions, 'crm.quote.delete')
const canSend = () => hasPermission(auth.permissions, 'crm.quote.send')
const canAccept = () => hasPermission(auth.permissions, 'crm.quote.accept')
const canConvert = () => hasPermission(auth.permissions, 'crm.order.convert')

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

const {
  loading, items, total, page, pageSize, views, activeViewId, advancedFilters, advancedFilterVisible,
  searchKeyword, saveViewVisible, saveViewName, saveViewPinned, saveViewDefault, saveViewPublic,
  activeView, hasDraftFilters, hasTemporaryFilter, advancedFilterCount, defaultTableSort, tableSortKey,
  canSaveView, canManagePublic, loadViews, load, onSearch, onSearchClear, onViewChange,
  openAdvancedFilter, applyAdvancedFilters, openSaveView, submitSaveView, onViewsRefresh, clearActiveView,
  clearTemporaryFilters, onPageChange, initRouteView, watchRouteView,
} = useCrmViewList({
  entityType: 'quote',
  listPath: '/crm/quotes',
  fields,
  extraParams: computed(() => ({ status: statusFilter.value })),
  onResetExtra: () => { statusFilter.value = '' },
  fetcher: async (params) => {
    const { data } = await crmApi.listQuotes(params)
    return { items: data.items || [], total: data.total || 0, filters_applied: data.filters_applied }
  },
})

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

function formatAmount(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function formatDate(v) { return v ? String(v).replace('T', ' ').slice(0, 10) : '' }

let stopRouteWatch = null
onMounted(async () => {
  initRouteView()
  await Promise.all([loadSchema(), loadMembers()])
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
        <el-button v-if="canCreate()" type="primary" @click="openCreate">新建报价</el-button>
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
          class="crm-list-status-filter"
          :disabled="!!activeViewId"
          @change="() => { page = 1; load() }"
        >
          <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
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
        <el-table-column prop="quote_number" label="报价单号" width="160" fixed="left" show-overflow-tooltip />
        <el-table-column prop="subject" label="主题" min-width="200" show-overflow-tooltip />
        <el-table-column label="金额" width="140" align="right">
          <template #default="{ row }">¥{{ formatAmount(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="有效期" width="120">
          <template #default="{ row }">{{ formatDate(row.valid_until) || '—' }}</template>
        </el-table-column>
        <el-table-column label="负责人" width="110" fixed="right">
          <template #default="{ row }">{{ resolveMemberName(row.owner_user_id) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right" align="center" @click.stop>
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
            <el-button v-if="canEdit() && row.status === 'draft'" link @click.stop="openEdit(row)">编辑</el-button>
            <el-button v-if="canSend() && row.status === 'draft'" link type="warning" @click.stop="handleSend(row)">发送</el-button>
            <el-button v-if="canAccept() && row.status === 'sent'" link type="success" @click.stop="handleAccept(row)">接受</el-button>
            <el-button v-if="canConvert() && row.status === 'accepted'" link type="primary" @click.stop="handleConvert(row)">转订单</el-button>
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
.crm-list-status-filter { width: 120px; }
</style>
