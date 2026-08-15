<script setup>
/**
 * P11 订阅台账。对照 PRD 06-平台端UI.html #p11 · #p11-todo · #p11a · #p11b · #p11c · #p11d · #p11e
 * 默认列：开通单号、商家、套餐、订阅类型、生效起、生效止、开通时间、开通人、状态、操作
 * 列设置可选：tenant_id、套餐快照版本
 * 缺口：结案不发站内信（通知管家未接通）；导出完成站内信本批不接。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminApi } from '../../../api/client'
import { useAuthStore } from '../../../stores/auth'
import { formatDateTime } from '../../../utils/datetime'

const COLUMN_KEY = 'shop-subscription-list-columns'
const ALL_COLUMNS = [
  { key: 'subscription_no', label: '开通单号', locked: true, defaultVisible: true },
  { key: 'merchant_name', label: '商家', locked: true, defaultVisible: true },
  { key: 'plan_name', label: '套餐', defaultVisible: true },
  { key: 'plan_type', label: '订阅类型', defaultVisible: true },
  { key: 'effective_at', label: '生效起', defaultVisible: true },
  { key: 'expires_at', label: '生效止', defaultVisible: true },
  { key: 'created_at', label: '开通时间', defaultVisible: true },
  { key: 'operator_name', label: '开通人', defaultVisible: true },
  { key: 'status', label: '状态', locked: true, defaultVisible: true },
  { key: 'ops', label: '操作', locked: true, defaultVisible: true },
  { key: 'tenant_id', label: '租户编号', defaultVisible: false },
  { key: 'snapshot_ver', label: '套餐快照版本', defaultVisible: false },
]

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const canManage = computed(() => auth.hasPlatformShopPermission('platform.shop.subscription.manage'))

const loading = ref(false)
const exporting = ref(false)
const exportDialog = ref(false)
const exportTask = ref(null)
const exportScope = ref('当前筛选')
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchQ = ref('')
const viewSel = ref('all')
const filterStatus = ref('')
const filterPlan = ref('')
const advExpanded = ref(false)
const sortBy = ref('created_at')
const sortDir = ref('desc')
const plans = ref([])
const merchants = ref([])
const todos = ref([])
const todoCollapsed = ref(false)
const columnDialogVisible = ref(false)
const columnDraft = ref([])
const visibleKeys = ref(ALL_COLUMNS.filter((c) => c.defaultVisible).map((c) => c.key))

const openVisible = ref(false)
const replaceVisible = ref(false)
const renewVisible = ref(false)
const cancelVisible = ref(false)
const detailVisible = ref(false)
const processVisible = ref(false)
const cancelReqVisible = ref(false)
const submitting = ref(false)
const current = ref(null)
const processTodo = ref(null)
const cancelReqForm = reactive({ tenant_id: '', log_id: '', note: '' })

const openForm = reactive({
  tenant_id: '',
  purchase_mode: 'replace',
  plan_code: '',
  paid_yuan: 0,
  effective_at: '',
  expires_at: '',
  remark: '',
})
const replaceForm = reactive({
  target_plan_code: '',
  paid_yuan: 0,
  effective_at: '',
  expires_at: '',
  remark: '',
})
const renewForm = reactive({
  paid_yuan: 0,
  effective_at: '',
  expires_at: '',
  remark: '',
})
const processForm = reactive({ remark: '', effective_at: '', expires_at: '' })
const openPreview = ref('')
const replacePreview = ref('')

const STATUS_TAG = {
  active: 'success',
  expiring_soon: 'warning',
  expired: 'info',
  cancelled: 'info',
  superseded: 'info',
}

function isColVisible(key) {
  return visibleKeys.value.includes(key)
}

function centsToYuan(c) {
  return ((Number(c) || 0) / 100).toFixed(2)
}

function yuanToCents(v) {
  return Math.round(Number(v || 0) * 100)
}

function todayStr() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function addDays(iso, days) {
  const d = new Date(`${iso}T00:00:00`)
  d.setDate(d.getDate() + days)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function displayLabel(row) {
  if (row.display_status === 'expiring_soon') return '即将到期'
  return row.status_label || row.status
}

function periodLabel(p) {
  return p === 'monthly' ? '月' : '年'
}

function selectedPlan(code) {
  return plans.value.find((p) => p.code === code)
}

const openCatalog = computed(() => selectedPlan(openForm.plan_code))
const replaceCatalog = computed(() => selectedPlan(replaceForm.target_plan_code))
const filteredOpenPlans = computed(() => {
  if (openForm.purchase_mode === 'stack') {
    return plans.value.filter((p) => p.plan_type === 'addon' && p.stackable)
  }
  return plans.value.filter((p) => p.plan_type === 'main')
})
const replacePlans = computed(() => {
  const cur = current.value
  const group = cur?.plan_snapshot?.replace_group
  const order = cur?.plan_snapshot?.sort_order ?? 0
  return plans.value.filter(
    (p) => p.plan_type === 'main' && (!group || p.replace_group === group) && (p.sort_order || 0) > order,
  )
})

function sortIcon(prop) {
  if (sortBy.value !== prop) return '↕'
  return sortDir.value === 'asc' ? '↑' : '↓'
}

function toggleSort(prop) {
  if (sortBy.value === prop) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else {
    sortBy.value = prop
    sortDir.value = 'desc'
  }
  page.value = 1
  load()
}

function listParams() {
  return {
    page: page.value,
    page_size: pageSize.value,
    q: searchQ.value.trim() || undefined,
    status: filterStatus.value || undefined,
    plan_code: filterPlan.value || undefined,
    view: viewSel.value === 'renewal' ? 'renewal' : undefined,
    sort_by: sortBy.value,
    sort_dir: sortDir.value,
  }
}

async function loadTodos() {
  if (!canManage.value) {
    todos.value = []
    return
  }
  try {
    const { data } = await adminApi.listShopPendingRenewals()
    todos.value = data.items || []
  } catch {
    todos.value = []
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopSubscriptions(listParams())
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  load()
}

function downloadBlob(data, filename) {
  const blob = data instanceof Blob ? data : new Blob([data])
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function exportList(mode) {
  exporting.value = true
  try {
    const body = { ...listParams() }
    delete body.page
    delete body.page_size
    if (mode === 'columns') {
      body.columns = visibleKeys.value.filter((k) => k !== 'ops')
    }
    const { data } = await adminApi.createShopSubscriptionExport(body)
    exportTask.value = data
    exportScope.value = mode === 'columns' ? '列配置' : '当前筛选'
    exportDialog.value = true
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

async function downloadExportFile() {
  if (!exportTask.value?.id) return
  try {
    const res = await adminApi.getShopSubscriptionExportFile(exportTask.value.id)
    downloadBlob(res.data, exportTask.value.file_name || 'shop-subscriptions.csv')
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

function goMerchant(row) {
  if (row?.tenant_id) router.push(`/admin/shop/merchants/${row.tenant_id}`)
}

function showReplace(row) {
  return canManage.value && row.status === 'active' && row.plan_type === 'main' && !row.has_pending_renewal
}
function showProcess(row) {
  return canManage.value && row.has_pending_renewal
}
function showRenew(row) {
  if (!canManage.value) return false
  if (row.has_pending_renewal) return false
  if (row.status === 'expired') return true
  return row.plan_type === 'addon' && row.status === 'active'
}
function showCancelAddon(row) {
  return canManage.value && row.plan_type === 'addon' && row.status === 'active'
}

function resetOpen() {
  openForm.tenant_id = ''
  openForm.purchase_mode = 'replace'
  openForm.plan_code = ''
  openForm.paid_yuan = 0
  openForm.effective_at = todayStr()
  openForm.expires_at = addDays(todayStr(), 364)
  openForm.remark = ''
  openPreview.value = ''
}

async function loadMergePreview(tenantId, planCode, mode) {
  if (!tenantId || !planCode) return ''
  const { data } = await adminApi.getShopMerchantEntitlements(tenantId, {
    preview_plan: planCode,
    preview_mode: mode,
  })
  return data.preview_text || (data.preview_lines || []).join(' · ') || ''
}

function onOpenPlanChange(code) {
  const p = selectedPlan(code)
  if (!p) return
  openForm.paid_yuan = Number(centsToYuan(p.price_cents))
  const start = openForm.effective_at || todayStr()
  openForm.expires_at = p.billing_period === 'monthly' ? addDays(start, 29) : addDays(start, 364)
}

watch(
  () => openForm.purchase_mode,
  () => {
    openForm.plan_code = ''
  },
)

function openCreate() {
  resetOpen()
  openVisible.value = true
}

async function submitOpen() {
  if (!openForm.tenant_id || !openForm.plan_code) {
    ElMessage.error('请选择商家与目标套餐')
    return
  }
  const catalog = openCatalog.value?.price_cents || 0
  const paid = yuanToCents(openForm.paid_yuan)
  if ((paid === 0 || paid !== catalog) && !openForm.remark.trim()) {
    ElMessage.error('0 元/议价须填写原因')
    return
  }
  submitting.value = true
  try {
    await adminApi.createShopSubscription({
      tenant_id: openForm.tenant_id,
      plan_code: openForm.plan_code,
      purchase_mode: openForm.purchase_mode,
      catalog_price_cents: catalog,
      paid_amount_cents: paid,
      effective_at: openForm.effective_at || undefined,
      expires_at: openForm.expires_at || undefined,
      remark: openForm.remark || undefined,
      source: 'manual',
    })
    ElMessage.success('开通成功')
    openVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '开通失败')
  } finally {
    submitting.value = false
  }
}

function openReplace(row) {
  current.value = row
  replaceForm.target_plan_code = ''
  replaceForm.paid_yuan = 0
  replaceForm.effective_at = todayStr()
  replaceForm.expires_at = addDays(todayStr(), 364)
  replaceForm.remark = ''
  replacePreview.value = ''
  replaceVisible.value = true
}

watch(
  () => `${openForm.tenant_id}|${openForm.plan_code}|${openForm.purchase_mode}`,
  async () => {
    openPreview.value = ''
    if (!openForm.tenant_id || !openForm.plan_code) return
    try {
      openPreview.value = await loadMergePreview(
        openForm.tenant_id,
        openForm.plan_code,
        openForm.purchase_mode,
      )
    } catch {
      openPreview.value = ''
    }
  },
)

watch(
  () => replaceForm.target_plan_code,
  (code) => {
    const p = selectedPlan(code)
    if (!p) return
    replaceForm.paid_yuan = Number(centsToYuan(p.price_cents))
    replaceForm.expires_at =
      p.billing_period === 'monthly' ? addDays(replaceForm.effective_at, 29) : addDays(replaceForm.effective_at, 364)
  },
)

watch(
  () => `${current.value?.tenant_id || ''}|${replaceForm.target_plan_code}`,
  async () => {
    replacePreview.value = ''
    const tenantId = current.value?.tenant_id
    if (!tenantId || !replaceForm.target_plan_code) return
    try {
      replacePreview.value = await loadMergePreview(tenantId, replaceForm.target_plan_code, 'replace')
    } catch {
      replacePreview.value = ''
    }
  },
)

async function submitReplace() {
  if (!current.value || !replaceForm.target_plan_code) {
    ElMessage.error('请选择目标套餐')
    return
  }
  const catalog = replaceCatalog.value?.price_cents || 0
  const paid = yuanToCents(replaceForm.paid_yuan)
  if ((paid === 0 || paid !== catalog) && !replaceForm.remark.trim()) {
    ElMessage.error('0 元/议价须填写原因')
    return
  }
  submitting.value = true
  try {
    await adminApi.replaceShopSubscription(current.value.id, {
      target_plan_code: replaceForm.target_plan_code,
      catalog_price_cents: catalog,
      paid_amount_cents: paid,
      effective_at: replaceForm.effective_at || undefined,
      expires_at: replaceForm.expires_at || undefined,
      remark: replaceForm.remark || undefined,
    })
    ElMessage.success('已换档')
    replaceVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '换档失败')
  } finally {
    submitting.value = false
  }
}

function openRenew(row) {
  current.value = row
  const catalog = row.catalog_price_cents || 0
  renewForm.paid_yuan = Number(centsToYuan(catalog))
  const nextStart = addDays(String(row.expires_at_inclusive).slice(0, 10), 1)
  renewForm.effective_at = nextStart
  renewForm.expires_at = row.billing_period === 'monthly' ? addDays(nextStart, 29) : addDays(nextStart, 364)
  renewForm.remark = ''
  renewVisible.value = true
}

async function submitRenew() {
  if (!current.value) return
  const catalog = current.value.catalog_price_cents || 0
  const paid = yuanToCents(renewForm.paid_yuan)
  if ((paid === 0 || paid !== catalog) && !renewForm.remark.trim()) {
    ElMessage.error('0 元/议价须填写原因')
    return
  }
  submitting.value = true
  try {
    await adminApi.renewShopSubscription(current.value.id, {
      catalog_price_cents: catalog,
      paid_amount_cents: paid,
      effective_at: renewForm.effective_at || undefined,
      expires_at: renewForm.expires_at || undefined,
      remark: renewForm.remark || undefined,
    })
    ElMessage.success('已续费')
    renewVisible.value = false
    await Promise.all([load(), loadTodos()])
  } catch (e) {
    ElMessage.error(e.message || '续费失败')
  } finally {
    submitting.value = false
  }
}

function openCancelAddon(row) {
  current.value = row
  cancelVisible.value = true
}

async function submitCancelAddon() {
  if (!current.value) return
  submitting.value = true
  try {
    await adminApi.cancelShopSubscription(current.value.id, {})
    ElMessage.success('已取消加购')
    cancelVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '取消失败')
  } finally {
    submitting.value = false
  }
}

async function openDetail(row) {
  try {
    const { data } = await adminApi.getShopSubscription(row.id)
    current.value = data
    detailVisible.value = true
  } catch (e) {
    ElMessage.error(e.message || '无查看权限')
  }
}

function findTodoForTenant(tenantId) {
  return todos.value.find((t) => t.tenant_id === tenantId)
}

function openProcess(rowOrTodo) {
  const todo =
    rowOrTodo.service_log_id ? rowOrTodo : findTodoForTenant(rowOrTodo.tenant_id)
  if (!todo) {
    ElMessage.info('未找到待处理续费申请')
    return
  }
  processTodo.value = todo
  processForm.remark = ''
  processForm.effective_at = todayStr()
  processForm.expires_at = addDays(todayStr(), 364)
  processVisible.value = true
}

async function submitProcess() {
  const todo = processTodo.value
  if (!todo) return
  submitting.value = true
  try {
    const mode = todo.purchase_mode === 'stack' ? 'stack' : 'replace'
    await adminApi.createShopSubscription({
      tenant_id: todo.tenant_id,
      plan_code: todo.target_plan,
      purchase_mode: mode,
      catalog_price_cents: todo.catalog_price_cents ?? undefined,
      paid_amount_cents: todo.quoted_amount_cents ?? 0,
      effective_at: processForm.effective_at || undefined,
      expires_at: processForm.expires_at || undefined,
      remark: processForm.remark || '对公已到账',
      source: 'renew',
      renewal_request_id: todo.service_log_id,
    })
    ElMessage.success('已开通并结案')
    processVisible.value = false
    await Promise.all([load(), loadTodos()])
  } catch (e) {
    ElMessage.error(e.message || '开通失败')
  } finally {
    submitting.value = false
  }
}

async function submitPark() {
  const todo = processTodo.value
  if (!todo) return
  submitting.value = true
  try {
    await adminApi.markShopRenewalProcessing(todo.tenant_id, todo.service_log_id)
    ElMessage.success('已暂存为处理中')
    processVisible.value = false
    await loadTodos()
  } catch (e) {
    ElMessage.error(e.message || '暂存失败')
  } finally {
    submitting.value = false
  }
}

async function submitRevert() {
  const todo = processTodo.value
  if (!todo) return
  submitting.value = true
  try {
    await adminApi.revertShopRenewalPending(todo.tenant_id, todo.service_log_id)
    ElMessage.success('已退回待处理')
    processTodo.value = { ...todo, status: 'pending', status_label: '待处理' }
    await loadTodos()
  } catch (e) {
    ElMessage.error(e.message || '退回失败')
  } finally {
    submitting.value = false
  }
}

function openCancelReq(todo) {
  if (!todo) return
  if (todo.status === 'processing') {
    ElMessage.warning('处理中须先退回待处理')
    return
  }
  cancelReqForm.tenant_id = todo.tenant_id
  cancelReqForm.log_id = todo.service_log_id
  cancelReqForm.note = ''
  cancelReqVisible.value = true
}

async function submitCancelReq() {
  if ((cancelReqForm.note || '').trim().length < 4) {
    ElMessage.error('请填写取消原因')
    return
  }
  submitting.value = true
  try {
    await adminApi.cancelShopRenewalRequest(
      cancelReqForm.tenant_id,
      cancelReqForm.log_id,
      cancelReqForm.note.trim(),
    )
    ElMessage.success('已取消申请')
    cancelReqVisible.value = false
    processVisible.value = false
    await Promise.all([load(), loadTodos()])
  } catch (e) {
    ElMessage.error(e.message || '取消失败')
  } finally {
    submitting.value = false
  }
}

function openColumnDialog() {
  columnDraft.value = ALL_COLUMNS.map((c) => ({
    ...c,
    visible: visibleKeys.value.includes(c.key),
  }))
  columnDialogVisible.value = true
}

function saveColumns() {
  visibleKeys.value = columnDraft.value.filter((c) => c.visible || c.locked).map((c) => c.key)
  localStorage.setItem(COLUMN_KEY, JSON.stringify(visibleKeys.value))
  columnDialogVisible.value = false
}

onMounted(async () => {
  try {
    const saved = JSON.parse(localStorage.getItem(COLUMN_KEY) || 'null')
    if (Array.isArray(saved) && saved.length) visibleKeys.value = saved
  } catch {
    /* ignore */
  }
  if (route.query.todo === 'renewal' || route.query.view === 'renewal') viewSel.value = 'renewal'
  if (route.query.status) filterStatus.value = String(route.query.status)
  if (route.query.plan_code) filterPlan.value = String(route.query.plan_code)
  const [mres, pres] = await Promise.all([
    adminApi.listShopMerchants({ page_size: 100, onboarding_status: 'active' }),
    adminApi.listShopPlanTemplates({ published: true, page_size: 50 }),
  ])
  merchants.value = (mres.data.items || []).filter((m) => m.merchant_id)
  plans.value = pres.data.items || []
  await Promise.all([load(), loadTodos()])
})

watch(pageSize, () => {
  page.value = 1
  load()
})
</script>

<template>
  <div class="page-card" data-testid="shop-subscription-page">
    <div v-if="canManage" class="todo-banner" data-testid="shop-renewal-todo">
      <div class="todo-banner__hd">
        <div>
          <div class="todo-banner__title">待处理续费申请 · {{ todos.length }}</div>
          <div class="todo-banner__sub">商家管家提交后在此处理，开通成功后自动将服务记录标为已完成。</div>
        </div>
        <el-button text @click="todoCollapsed = !todoCollapsed">{{ todoCollapsed ? '展开' : '收起' }}</el-button>
      </div>
      <div v-show="!todoCollapsed" class="todo-list">
        <div v-for="t in todos" :key="t.service_log_id" class="todo-item">
          <div>
            <b>{{ t.display_name }}</b>
            · {{ t.target_plan || t.plan_label || '套餐' }}
            <el-tag v-if="t.status === 'processing'" type="warning" size="small" style="margin-left: 6px">处理中</el-tag>
            <span v-if="t.quoted_amount_cents != null"> · ¥{{ centsToYuan(t.quoted_amount_cents) }}</span>
            · {{ t.operator_name || '管家' }}
            · {{ formatDateTime(t.created_at) }}
            <div class="todo-item__note">{{ t.content }}</div>
          </div>
          <div class="todo-item__ops">
            <el-button type="primary" size="small" @click="openProcess(t)">去处理</el-button>
            <el-button link type="primary" @click="goMerchant(t)">查看商家</el-button>
            <el-button link :disabled="t.status === 'processing'" @click="openCancelReq(t)">取消申请</el-button>
          </div>
        </div>
      </div>
    </div>

    <div class="toolbar">
      <el-select v-model="viewSel" style="width: 150px" @change="onSearch">
        <el-option label="全部订阅" value="all" />
        <el-option label="待处理续费" value="renewal" />
      </el-select>
      <el-input
        v-model="searchQ"
        clearable
        placeholder="订阅单号 / 商家名"
        style="width: 220px"
        @keyup.enter="onSearch"
        @clear="onSearch"
      />
      <el-select v-model="filterStatus" clearable placeholder="状态" style="width: 130px" @change="onSearch">
        <el-option label="生效中" value="active" />
        <el-option label="已到期" value="expired" />
        <el-option label="已取消" value="cancelled" />
        <el-option label="已换档" value="superseded" />
      </el-select>
      <el-select v-model="filterPlan" clearable placeholder="套餐" style="width: 160px" @change="onSearch">
        <el-option v-for="p in plans" :key="p.code" :label="p.name" :value="p.code" />
      </el-select>
      <el-button :type="advExpanded ? 'primary' : 'default'" plain @click="advExpanded = !advExpanded">高级筛选</el-button>
      <div class="toolbar-right">
        <el-dropdown trigger="click" @command="exportList">
          <el-button :loading="exporting">导出 ▾</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="current">当前筛选</el-dropdown-item>
              <el-dropdown-item command="columns">列配置</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="openColumnDialog">列设置</el-button>
        <el-button v-if="canManage" type="primary" @click="openCreate">人工开通（主套餐/叠加）</el-button>
      </div>
    </div>
    <p v-if="advExpanded" class="adv-hint">可按订阅单号/商家名搜索，状态与套餐筛选可叠加；视图「待处理续费」仅列出有申请的订阅。</p>

    <el-table v-loading="loading" :data="items" border stripe size="small" :row-class-name="({ row }) => (row.display_status === 'expiring_soon' ? 'row-warn' : '')">
      <el-table-column v-if="isColVisible('subscription_no')" min-width="150">
        <template #header>
          <span class="th-sort" @click="toggleSort('subscription_no')">开通单号 {{ sortIcon('subscription_no') }}</span>
        </template>
        <template #default="{ row }">{{ row.subscription_no }}</template>
      </el-table-column>
      <el-table-column v-if="isColVisible('merchant_name')" min-width="140">
        <template #header>
          <span class="th-sort" @click="toggleSort('merchant')">商家 {{ sortIcon('merchant') }}</span>
        </template>
        <template #default="{ row }">
          <el-button link type="primary" @click="goMerchant(row)">{{ row.merchant_display_name }}</el-button>
          <el-tag v-if="row.has_pending_renewal" size="small" type="warning" style="margin-left: 4px">续费申请</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="isColVisible('plan_name')" prop="plan_name" label="套餐" min-width="120" />
      <el-table-column v-if="isColVisible('plan_type')" label="订阅类型" width="100">
        <template #default="{ row }">{{ row.plan_type_label }}</template>
      </el-table-column>
      <el-table-column v-if="isColVisible('effective_at')" width="120">
        <template #header>
          <span class="th-sort" @click="toggleSort('effective_at')">生效起 {{ sortIcon('effective_at') }}</span>
        </template>
        <template #default="{ row }">{{ row.effective_at }}</template>
      </el-table-column>
      <el-table-column v-if="isColVisible('expires_at')" width="120">
        <template #header>
          <span class="th-sort" @click="toggleSort('expires_at')">生效止 {{ sortIcon('expires_at') }}</span>
        </template>
        <template #default="{ row }">
          <span :class="{ 'exp-warn': row.display_status === 'expiring_soon' }">{{ row.expires_at_inclusive }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="isColVisible('created_at')" width="160">
        <template #header>
          <span class="th-sort" @click="toggleSort('created_at')">开通时间 {{ sortIcon('created_at') }}</span>
        </template>
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column v-if="isColVisible('operator_name')" label="开通人" width="110">
        <template #default="{ row }">{{ row.operator_name || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="isColVisible('status')" label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="STATUS_TAG[row.display_status] || STATUS_TAG[row.status] || 'info'">
            {{ displayLabel(row) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="isColVisible('tenant_id')" label="租户编号" min-width="160">
        <template #default="{ row }">{{ row.tenant_id }}</template>
      </el-table-column>
      <el-table-column v-if="isColVisible('snapshot_ver')" label="套餐快照版本" width="120">
        <template #default="{ row }">{{ row.plan_snapshot?.version || row.plan_snapshot?.plan_code || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="isColVisible('ops')" label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button v-if="showProcess(row)" link type="primary" @click="openProcess(row)">处理续费</el-button>
          <el-button v-if="showReplace(row)" link type="primary" @click="openReplace(row)">换档</el-button>
          <el-button v-if="showRenew(row)" link type="primary" @click="openRenew(row)">
            {{ row.status === 'expired' ? '续费/重开' : '续费' }}
          </el-button>
          <el-button v-if="showCancelAddon(row)" link @click="openCancelAddon(row)">取消</el-button>
          <el-button link @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <span>共 {{ total }} 条</span>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="sizes, prev, pager, next"
        @current-change="load"
      />
    </div>

    <el-dialog v-model="openVisible" title="人工开通" width="520px">
      <el-form label-width="140px">
        <el-form-item label="商家" required>
          <el-select v-model="openForm.tenant_id" filterable style="width: 100%">
            <el-option v-for="m in merchants" :key="m.tenant_id" :label="m.display_name" :value="m.tenant_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开通方式" required>
          <el-radio-group v-model="openForm.purchase_mode">
            <el-radio value="stack">叠加</el-radio>
            <el-radio value="replace">主套餐</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="选择套餐" required>
          <el-select v-model="openForm.plan_code" style="width: 100%" @change="onOpenPlanChange">
            <el-option v-for="p in filteredOpenPlans" :key="p.code" :label="p.name" :value="p.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="套餐标价（只读）">
          ¥{{ centsToYuan(openCatalog?.price_cents) }} / {{ periodLabel(openCatalog?.billing_period) }}
        </el-form-item>
        <el-form-item label="应付金额" required>
          <el-input-number v-model="openForm.paid_yuan" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效起" required>
          <el-date-picker v-model="openForm.effective_at" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效止" required>
          <el-date-picker v-model="openForm.expires_at" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="运营备注（选填）">
          <el-input v-model="openForm.remark" type="textarea" />
        </el-form-item>
        <el-form-item label="合并预览（只读）">
          <div data-testid="shop-merge-preview">{{ openPreview || '选择商家与套餐后显示' }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="openVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitOpen">确认开通</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="replaceVisible" :title="`换档 · ${current?.merchant_display_name || ''}`" width="520px">
      <el-form label-width="140px">
        <el-form-item label="商家（只读）">{{ current?.merchant_display_name }}</el-form-item>
        <el-form-item label="当前套餐（只读）">{{ current?.plan_name }}（生效中）→ 将变为已换档</el-form-item>
        <el-form-item label="目标套餐" required>
          <el-select v-model="replaceForm.target_plan_code" style="width: 100%">
            <el-option v-for="p in replacePlans" :key="p.code" :label="p.name" :value="p.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="套餐标价（只读）">
          ¥{{ centsToYuan(replaceCatalog?.price_cents) }} / {{ periodLabel(replaceCatalog?.billing_period) }}
        </el-form-item>
        <el-form-item label="换档金额" required>
          <el-input-number v-model="replaceForm.paid_yuan" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效起" required>
          <el-date-picker v-model="replaceForm.effective_at" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效止" required>
          <el-date-picker v-model="replaceForm.expires_at" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="运营备注（选填）">
          <el-input v-model="replaceForm.remark" type="textarea" />
        </el-form-item>
        <el-form-item label="合并预览（只读）">
          <div>{{ replacePreview || '选择目标套餐后显示' }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="replaceVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitReplace">确认换档</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="renewVisible" :title="`续费 · ${current?.merchant_display_name || ''}`" width="480px">
      <el-form label-width="140px">
        <el-form-item label="商家（只读）">{{ current?.merchant_display_name }}</el-form-item>
        <el-form-item label="套餐标价（只读）">¥{{ centsToYuan(current?.catalog_price_cents) }}</el-form-item>
        <el-form-item label="续费金额" required>
          <el-input-number v-model="renewForm.paid_yuan" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="新生效区间" required>
          <el-date-picker v-model="renewForm.effective_at" value-format="YYYY-MM-DD" style="width: 48%" />
          <span> ～ </span>
          <el-date-picker v-model="renewForm.expires_at" value-format="YYYY-MM-DD" style="width: 48%" />
        </el-form-item>
        <el-form-item label="运营备注（选填）">
          <el-input v-model="renewForm.remark" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="renewVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRenew">确认续费</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="cancelVisible" :title="`取消加购 · ${current?.merchant_display_name || ''}`" width="480px">
      <el-form label-width="140px">
        <el-form-item label="商家（只读）">{{ current?.merchant_display_name }}</el-form-item>
        <el-form-item label="加购套餐（只读）">{{ current?.plan_name }}</el-form-item>
        <el-form-item label="影响说明（只读）">取消后当月剩余额度按合并重算；已发送短信不回滚</el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cancelVisible = false">返回</el-button>
        <el-button type="warning" :loading="submitting" @click="submitCancelAddon">确认取消</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" size="520px" :title="`订阅详情 · ${current?.merchant_display_name || ''}`">
      <template v-if="current">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="商家（只读）">
            <el-button link type="primary" @click="goMerchant(current)">{{ current.merchant_display_name }}</el-button>
          </el-descriptions-item>
          <el-descriptions-item label="套餐（只读）">{{ current.plan_name }}</el-descriptions-item>
          <el-descriptions-item label="开通模式（只读）">{{ current.purchase_mode === 'stack' ? '叠加' : '主套餐' }}</el-descriptions-item>
          <el-descriptions-item label="生效区间（只读）">{{ current.effective_at }} ～ {{ current.expires_at_inclusive }}</el-descriptions-item>
          <el-descriptions-item label="套餐标价（只读）">¥{{ centsToYuan(current.catalog_price_cents) }}</el-descriptions-item>
          <el-descriptions-item label="实收金额（只读）">¥{{ centsToYuan(current.paid_amount_cents) }}</el-descriptions-item>
          <el-descriptions-item label="状态（只读）">{{ displayLabel(current) }}</el-descriptions-item>
          <el-descriptions-item label="权益快照（只读）">{{ current.plan_name }} · {{ current.plan_code }}</el-descriptions-item>
          <el-descriptions-item label="审计日志（只读）">开通 {{ formatDateTime(current.created_at) }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>

    <el-dialog v-model="processVisible" :title="`处理续费申请 · ${processTodo?.display_name || ''}`" width="560px">
      <el-form v-if="processTodo" label-width="140px">
        <el-form-item label="管家备注（只读）">{{ processTodo.content }}</el-form-item>
        <el-form-item label="续费金额（只读）">¥{{ centsToYuan(processTodo.quoted_amount_cents) }}</el-form-item>
        <el-form-item label="套餐标价（只读）">¥{{ centsToYuan(processTodo.catalog_price_cents) }}</el-form-item>
        <el-form-item label="选择套餐">{{ processTodo.target_plan }}</el-form-item>
        <el-form-item label="开通方式">{{ processTodo.purchase_mode === 'stack' ? '叠加' : '主套餐（续期）' }}</el-form-item>
        <el-form-item label="生效起" required>
          <el-date-picker v-model="processForm.effective_at" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效止" required>
          <el-date-picker v-model="processForm.expires_at" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="运营备注（选填）">
          <el-input v-model="processForm.remark" placeholder="对公已到账" type="textarea" />
        </el-form-item>
        <el-form-item label="结案联动（只读）">确认开通后写订阅，并将服务记录标为已完成。结案通知管家未接通。</el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="processVisible = false">取消</el-button>
        <el-button
          v-if="processTodo?.status !== 'processing'"
          :loading="submitting"
          @click="submitPark"
        >暂存处理中</el-button>
        <el-button
          v-else
          :loading="submitting"
          @click="submitRevert"
        >退回待处理</el-button>
        <el-button
          :disabled="processTodo?.status === 'processing'"
          @click="openCancelReq(processTodo)"
        >取消申请</el-button>
        <el-button type="primary" :loading="submitting" @click="submitProcess">确认开通并结案</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="cancelReqVisible" title="取消申请" width="440px">
      <el-form label-width="120px">
        <el-form-item label="取消原因" required>
          <el-input v-model="cancelReqForm.note" type="textarea" placeholder="至少 4 字" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cancelReqVisible = false">返回</el-button>
        <el-button type="warning" :loading="submitting" @click="submitCancelReq">确认取消</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="columnDialogVisible" title="列设置" width="360px">
      <div v-for="col in columnDraft" :key="col.key" class="column-item">
        <el-checkbox v-model="col.visible" :disabled="col.locked">{{ col.label }}</el-checkbox>
      </div>
      <template #footer>
        <el-button @click="columnDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveColumns">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="exportDialog" title="导出任务" width="420px">
      <el-form v-if="exportTask" label-width="100px">
        <el-form-item label="范围">{{ exportScope }}</el-form-item>
        <el-form-item label="条数">{{ exportTask.row_count ?? 0 }} 条</el-form-item>
        <el-form-item label="状态">{{ exportTask.status === 'done' ? '已完成' : (exportTask.status || '—') }}</el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :disabled="exportTask?.status !== 'done'" @click="downloadExportFile">
          下载
        </el-button>
        <el-button @click="exportDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.todo-banner {
  border: 1px solid #ffd591;
  background: #fffbe6;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 16px;
}
.todo-banner__hd { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.todo-banner__title { font-weight: 600; color: #ad6800; margin-bottom: 4px; }
.todo-banner__sub { font-size: 12px; color: var(--el-text-color-secondary); }
.todo-list { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
.todo-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid #ffe7ba;
  border-radius: 6px;
  font-size: 13px;
}
.todo-item__note { color: var(--el-text-color-secondary); margin-top: 4px; }
.todo-item__ops { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
.toolbar-right { margin-left: auto; display: flex; gap: 8px; }
.adv-hint { margin: 0 0 8px; font-size: 12px; color: var(--el-text-color-secondary); }
.pager { display: flex; align-items: center; justify-content: space-between; margin-top: 12px; }
.th-sort { cursor: pointer; user-select: none; }
.exp-warn { color: #cf1322; font-weight: 600; }
.column-item { margin-bottom: 8px; }
:deep(.row-warn) { background: #fffbe6; }
</style>
