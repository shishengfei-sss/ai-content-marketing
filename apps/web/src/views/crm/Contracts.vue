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
const { fields, loadSchema } = useEntitySchema('contract')
const { resolveMemberName, loadMembers, members } = useTeamMembers()

const statusFilter = ref('')

const dialogVisible = ref(false)
const editing = ref(false)
const saving = ref(false)
const customerOptions = ref([])
const customerLoading = ref(false)
const form = ref(emptyForm())

const signVisible = ref(false)
const signForm = ref({ signed_amount: null, signed_at: '' })
const signingId = ref('')

function emptyForm() {
  return { id: '', customer_id: '', deal_id: '', quote_id: '', title: '', contract_type: 'new', amount: null, start_date: '', end_date: '', status: 'draft', file_url: '' }
}

const canCreate = () => hasPermission(auth.permissions, 'crm.contract.create')
const canEdit = () => hasPermission(auth.permissions, 'crm.contract.edit')
const canSign = () => hasPermission(auth.permissions, 'crm.contract.sign')
const canDelete = () => hasPermission(auth.permissions, 'crm.contract.delete')
const canConvert = () => hasPermission(auth.permissions, 'crm.order.convert')

const STATUS_META = {
  draft: { label: '草稿', type: 'info' },
  sent: { label: '已发送', type: 'warning' },
  signed: { label: '已签署', type: 'success' },
  executing: { label: '执行中', type: 'success' },
  expired: { label: '已过期', type: 'info' },
  terminated: { label: '已终止', type: 'danger' },
}
const TYPE_META = { new: '新签', renewal: '续约', addon: '增订' }
function statusMeta(s) { return STATUS_META[s] || { label: s, type: '' } }

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
    return { items: data.items || [], total: data.total || 0, filters_applied: data.filters_applied }
  },
})

async function searchCustomers(q = '') {
  customerLoading.value = true
  try {
    const { data } = await crmApi.listCustomers({ page: 1, page_size: 50, q })
    customerOptions.value = (data.items || []).map((c) => ({ id: c.id, company_name: c.company_name }))
  } catch { customerOptions.value = [] } finally { customerLoading.value = false }
}

function openCreate() {
  editing.value = false
  form.value = emptyForm()
  dialogVisible.value = true
}

async function openEdit(row) {
  editing.value = true
  const { data } = await crmApi.getContract(row.id)
  form.value = {
    id: data.id,
    customer_id: data.customer_id,
    deal_id: data.deal_id || '',
    quote_id: data.quote_id || '',
    title: data.title,
    contract_type: data.contract_type,
    amount: Number(data.amount),
    start_date: data.start_date ? String(data.start_date).slice(0, 10) : '',
    end_date: data.end_date ? String(data.end_date).slice(0, 10) : '',
    status: data.status,
    file_url: data.file_url || '',
  }
  if (data.customer_id) customerOptions.value = [{ id: data.customer_id, company_name: '(已绑定客户)' }]
  dialogVisible.value = true
}

async function submit() {
  if (!form.value.title?.trim()) { ElMessage.warning('请填写合同标题'); return }
  if (!form.value.customer_id) { ElMessage.warning('请选择客户'); return }
  saving.value = true
  try {
    const payload = {
      customer_id: form.value.customer_id,
      title: form.value.title.trim(),
      contract_type: form.value.contract_type,
      amount: form.value.amount ?? 0,
      start_date: form.value.start_date || null,
      end_date: form.value.end_date || null,
      status: form.value.status,
      file_url: form.value.file_url || null,
    }
    if (form.value.deal_id) payload.deal_id = form.value.deal_id
    if (form.value.quote_id) payload.quote_id = form.value.quote_id
    if (editing.value) {
      await crmApi.updateContract(form.value.id, payload)
      ElMessage.success('已保存')
    } else {
      await crmApi.createContract(payload)
      ElMessage.success('合同已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
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

async function handleConvert(row) {
  try {
    await ElMessageBox.confirm(`将合同「${row.title}」生成订单？（合同可重复生成订单）`, '生成订单')
    const { data } = await crmApi.convertContractToOrder(row.id)
    ElMessage.success('已生成订单')
    router.push(`/crm/orders/${data.order_id}`)
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '转化失败') }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除合同「${row.title}」？`, '删除')
    await crmApi.deleteContract(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

function goDetail(row) { router.push(`/crm/contracts/${row.id}`) }
function formatAmount(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function formatDate(v) { return v ? String(v).replace('T', ' ').slice(0, 10) : '' }

watch(dialogVisible, async (v) => { if (v) await searchCustomers('') })
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
        <el-table-column prop="contract_number" label="合同号" width="160" fixed="left" show-overflow-tooltip />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="类型" width="80" align="center">
          <template #default="{ row }">{{ TYPE_META[row.contract_type] || row.contract_type }}</template>
        </el-table-column>
        <el-table-column label="金额" width="130" align="right">
          <template #default="{ row }">¥{{ formatAmount(row.signed_amount != null ? row.signed_amount : row.amount) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }"><el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag></template>
        </el-table-column>
        <el-table-column label="生效期" width="220">
          <template #default="{ row }">{{ formatDate(row.start_date) }} ~ {{ formatDate(row.end_date) }}</template>
        </el-table-column>
        <el-table-column label="负责人" width="110" fixed="right">
          <template #default="{ row }">{{ resolveMemberName(row.owner_user_id) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right" align="center" @click.stop>
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
            <el-button v-if="canEdit() && row.status === 'draft'" link @click.stop="openEdit(row)">编辑</el-button>
            <el-button v-if="canSign() && row.status === 'draft'" link type="success" @click.stop="openSign(row)">签署</el-button>
            <el-button v-if="canConvert() && (row.status === 'signed' || row.status === 'executing')" link type="primary" @click.stop="handleConvert(row)">生成订单</el-button>
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

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑合同' : '新建合同'" width="600px" destroy-on-close>
      <el-form label-width="88px">
        <el-form-item label="标题" required><el-input v-model="form.title" maxlength="200" /></el-form-item>
        <el-form-item label="客户" required>
          <el-select v-model="form.customer_id" filterable remote :remote-method="searchCustomers" :loading="customerLoading" placeholder="搜索客户" style="width: 100%">
            <el-option v-for="c in customerOptions" :key="c.id" :label="c.company_name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="合同类型">
          <el-select v-model="form.contract_type">
            <el-option label="新签" value="new" />
            <el-option label="续约" value="renewal" />
            <el-option label="增订" value="addon" />
          </el-select>
        </el-form-item>
        <el-form-item label="金额">
          <el-input-number v-model="form.amount" :min="0" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效日">
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width: 200px" />
        </el-form-item>
        <el-form-item label="到期日">
          <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width: 200px" />
        </el-form-item>
        <el-form-item label="附件URL">
          <el-input v-model="form.file_url" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>

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
