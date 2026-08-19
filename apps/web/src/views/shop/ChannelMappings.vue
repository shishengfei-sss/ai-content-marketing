<script setup>
/**
 * 商品映射。对照 PRD 01-管理端UI.html #a14 · #a14-list · #a14a · #a14b · #a14c · 04#select-common
 * 列表/新建商品下拉按顶栏当前店铺过滤（04：A01–A14 按当前 shop_id）
 * 缺口：导出完成站内信本批不接。
 */
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/client'
import { submitShopExport, SHOP_EXPORT_COLUMN_MODE_LABELS } from '../../utils/shopExport'
import CrmColumnSettingsDialog from '../../components/crm/CrmColumnSettingsDialog.vue'
import ShopProductPickerPanel from '../../components/shop/ShopProductPickerPanel.vue'
import { useListColumnSettings } from '../../composables/useListColumnSettings'
import { useCurrentShop } from '../../composables/useCurrentShop'
import { authShopFileUrl } from '../../utils/shopContentUrl'
import { channelApiError, mappingBlockTip } from '../../utils/shopChannelMap'

const router = useRouter()
const route = useRoute()
const { currentId } = useCurrentShop()

const loading = ref(false)
const items = ref([])
const total = ref(0)
const statusCounts = ref({})
const configured = ref(true)
const selectedProductData = ref(null)
const productPickerRef = ref(null)
const PRODUCT_TYPE_LABEL = { course: '课程', digital: '资料', service: '服务' }
const settings = ref({
  douyin_shop_id: '',
  enabled_combos: ['1A'],
  has_webhook_secret: false,
  webhook_verified: false,
  demo_tools_enabled: false,
})
const demoToolsEnabled = computed(() => !!settings.value.demo_tools_enabled)
const demoOrderVisible = ref(false)
const demoOrderResult = ref(null)
const demoOrderBusyId = ref('')

const setupHint = computed(() => {
  if (!settings.value.douyin_shop_id) {
    return '请填写外部店铺 ID 并保存绑店'
  }
  if (!settings.value.has_webhook_secret) {
    return '绑店 ID 已保存，还需填写 Webhook 密钥并再次保存绑店'
  }
  return '请完成绑店与回调配置'
})
const query = reactive({
  page: 1,
  page_size: 20,
  status: '',
  q: '',
  external_audit_status: '',
  path: '',
  mapped_from: '',
  mapped_to: '',
})
const advOpen = ref(false)
const exporting = ref(false)

const createVisible = ref(false)
const wizardStep = ref(1)
const wizardBusy = ref(false)
const DY_CATEGORIES = [
  '教育培训 / 职业技能',
  '教育培训 / 考研考证',
  '生活服务 / 咨询辅导',
]
const form = reactive({
  product_id: '',
  combo: '1A',
  external_title: '',
  external_category: '教育培训 / 职业技能',
  sync_mode: 'create_new',
  channel_product_id: '',
})

const selectedProduct = computed(() => selectedProductData.value)
const pathOptions = computed(() => {
  const combos = settings.value.enabled_combos || ['1A']
  return combos.map((c) => ({
    value: c,
    label: c.endsWith('B') ? 'B 课程库路径' : 'A 官方 API',
  }))
})
const pathLabel = computed(() => (form.combo || '1A').slice(-1))

const logVisible = ref(false)
const logLoading = ref(false)
const logRow = ref(null)
const logItems = ref([])
const logTab = ref('all')
const LOG_TABS = [
  { key: 'all', label: '全部' },
  { key: 'sync', label: '同步' },
  { key: 'external_audit', label: '外部审核' },
  { key: 'webhook', label: '订单回调' },
  { key: 'status', label: '状态变更' },
]

const reasonVisible = ref(false)
const reasonRow = ref(null)
const resubmitting = ref(false)

const COL_STORAGE = 'shop.a14.columns'
const ALL_COLS = [
  { key: 'product_name', label: '本地商品', locked: true, defaultOn: true },
  { key: 'product_review_status', label: '商品审核', defaultOn: true },
  { key: 'channel_product_id', label: '外部商品 ID', defaultOn: true },
  { key: 'path_label', label: '路径', defaultOn: true },
  { key: 'status_label', label: '挂载状态', defaultOn: true },
  { key: 'external_audit_status', label: '外部审核', defaultOn: true },
  { key: 'created_at', label: '映射时间', defaultOn: true },
  { key: 'synced_at', label: '最近同步时间', defaultOn: false },
  { key: 'channel_label', label: '渠道', defaultOn: false },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]
const {
  visibleKeys,
  columnDialogVisible: colDialog,
  columnDraft,
  openColumnSettings,
  saveColumnSettings,
  isColVisible,
} = useListColumnSettings(ALL_COLS, COL_STORAGE)

const TABS = [
  { key: '', label: '全部映射' },
  { key: 'mapped', label: '已挂载' },
  { key: 'unmapped', label: '未挂载' },
  { key: 'blocked', label: '已阻断' },
  { key: 'paused', label: '暂停同步' },
]

const EVENT_LABEL = {
  listing_paused: '暂停',
  listing_resumed: '恢复',
  sync_succeeded: '同步',
  sync_failed: '同步',
  sync_started: '同步',
  map_attempt: '映射',
  unmount: '状态变更',
  auto_reject: '回调',
  force_unmount: '状态变更',
  external_audit_approved: '审核',
  external_audit_rejected: '审核',
  external_audit_resubmitted: '状态变更',
}

function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 16)
}
function tabCount(key) {
  if (!key) return statusCounts.value.all ?? total.value
  return statusCounts.value[key] ?? 0
}

function eventBadge(ev) {
  return EVENT_LABEL[ev] || '日志'
}

function logSummary(row) {
  const d = row.detail_json || {}
  if (d.summary) return d.summary
  if (row.event === 'listing_paused') return '商家暂停同步'
  if (row.event === 'listing_resumed') return '商家恢复同步'
  if (row.event === 'sync_succeeded') return `同步抖店成功 · ${d.channel_product_id || ''}`
  if (row.event === 'auto_reject') return `Webhook 拒单 · ${d.reason_code || ''}`
  if (row.event === 'map_attempt') return '创建映射 · 提交外部审核'
  if (row.event === 'unmount') return '解除映射'
  if (row.event === 'external_audit_rejected') {
    return `外部审核被拒 · ${d.reject_code || ''}`
  }
  if (row.event === 'external_audit_approved') return '外部审核通过 · mapped'
  if (row.event === 'external_audit_resubmitted') return '修改并重新提交外部审核'
  return row.event
}

const canResync = computed(
  () => logRow.value && (logRow.value.status === 'mapped' || logRow.value.status === 'paused')
)

async function loadSettings() {
  try {
    const { data } = await api.get('/api/v1/shop/channel-settings')
    configured.value = !!data.douyin_configured
    settings.value = {
      douyin_shop_id: data.douyin_shop_id || '',
      enabled_combos: data.enabled_combos?.length ? data.enabled_combos : ['1A'],
      has_webhook_secret: !!data.has_webhook_secret,
      webhook_verified: !!data.webhook_verified,
      demo_tools_enabled: !!data.demo_tools_enabled,
    }
  } catch (e) {
    configured.value = false
    if (e?.response?.status === 403) {
      ElMessage.warning('无公域对接查看权限，无法确认对接状态')
    }
  }
}

function clearPickedProduct() {
  form.product_id = ''
  nextTick(() => productPickerRef.value?.refresh())
}

function onPickProduct(row) {
  selectedProductData.value = row
  form.external_title = row?.name || ''
  form.channel_product_id = ''
  form.external_category = DY_CATEGORIES[0]
  form.sync_mode = 'create_new'
  if (wizardStep.value > 1) wizardStep.value = 1
}

function openWizard() {
  wizardStep.value = 1
  form.product_id = ''
  selectedProductData.value = null
  form.combo = (settings.value.enabled_combos || ['1A'])[0] || '1A'
  form.external_title = ''
  form.external_category = DY_CATEGORIES[0]
  form.sync_mode = 'create_new'
  form.channel_product_id = ''
  createVisible.value = true
  nextTick(() => productPickerRef.value?.refresh())
}

watch(
  () => form.product_id,
  (id) => {
    if (!id) selectedProductData.value = null
    form.channel_product_id = ''
    form.external_category = DY_CATEGORIES[0]
    form.sync_mode = 'create_new'
    if (wizardStep.value > 1) wizardStep.value = 1
  }
)

watch(
  () => form.combo,
  () => {
    form.channel_product_id = ''
    if (wizardStep.value > 1) wizardStep.value = 1
  }
)

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}

function wizardNext1() {
  if (!form.product_id) {
    ElMessage.warning('请选择本地商品')
    return
  }
  const blockTip = mappingBlockTip(selectedProduct.value)
  if (blockTip) {
    ElMessage.warning(blockTip)
    return
  }
  if (!form.combo) {
    ElMessage.warning('请选择对接路径')
    return
  }
  if (!settings.value.douyin_shop_id) {
    ElMessage.warning('外部店铺未绑定，请先完成公域对接')
    return
  }
  if (!form.external_title) form.external_title = selectedProduct.value?.name || ''
  wizardStep.value = 2
}

async function wizardSyncNext() {
  const title = (form.external_title || '').trim()
  if (title.length < 2 || title.length > 60) {
    ElMessage.warning('抖店展示标题须 2–60 字')
    return
  }
  if (!form.external_category) {
    ElMessage.warning('请选择抖店类目')
    return
  }
  wizardBusy.value = true
  try {
    const { data } = await api.post('/api/v1/shop/channel-mappings/preview-sync', {
      product_id: form.product_id,
      combo: form.combo,
      external_title: title,
      external_category: form.external_category,
      sync_mode: form.sync_mode,
    })
    form.channel_product_id = data.channel_product_id
    form.external_title = data.external_title
    wizardStep.value = 3
  } catch (e) {
    ElMessage.error(channelApiError(e, '同步失败'))
  } finally {
    wizardBusy.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/shop/channel-mappings', {
      params: {
        page: query.page,
        page_size: query.page_size,
        status: query.status || undefined,
        q: query.q || undefined,
        shop_id: currentId.value || undefined,
        external_audit_status: query.external_audit_status || undefined,
        path: query.path || undefined,
        mapped_from: query.mapped_from || undefined,
        mapped_to: query.mapped_to || undefined,
      },
    })
    items.value = data.items || []
    total.value = data.total || 0
    statusCounts.value = data.status_counts || {}
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function preloadWizardProduct(productId) {
  if (!productId) return false
  try {
    const { data } = await api.get(`/api/v1/shop/products/${productId}`)
    const blockTip = mappingBlockTip(data)
    if (blockTip) {
      ElMessage.warning(blockTip)
      return false
    }
    selectedProductData.value = data
    form.external_title = data.name || ''
    return true
  } catch {
    ElMessage.warning('无法加载预选商品，请手动选择')
    return false
  }
}

function selectTab(key) {
  query.status = key
  query.page = 1
  load()
}

function resetAdv() {
  query.path = ''
  query.external_audit_status = ''
  query.mapped_from = ''
  query.mapped_to = ''
  query.page = 1
  load()
}

function visibleExportColumns() {
  return visibleKeys.value.filter((k) => k !== 'ops')
}

async function exportCsv(mode) {
  exporting.value = true
  try {
    const body = {
      status: query.status || undefined,
      q: query.q || undefined,
      shop_id: currentId.value || undefined,
      external_audit_status: query.external_audit_status || undefined,
      path: query.path || undefined,
      mapped_from: query.mapped_from || undefined,
      mapped_to: query.mapped_to || undefined,
    }
    if (mode === 'columns') {
      body.columns = visibleExportColumns()
    }
    await submitShopExport(
      '/api/v1/shop/channel-mappings/export',
      body,
      '/api/v1/shop/channel-mappings/export-tasks',
      'shop-channel-mappings.csv',
      total.value,
    )
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}


async function createMapping() {
  if (!form.channel_product_id) {
    ElMessage.warning('请先完成步 2 同步')
    return
  }
  wizardBusy.value = true
  try {
    const { data } = await api.post('/api/v1/shop/channel-mappings', {
      product_id: form.product_id,
      channel_product_id: form.channel_product_id,
      channel: 'douyin',
      combo: form.combo,
      external_title: form.external_title,
      external_category: form.external_category,
      sync_mode: form.sync_mode,
      submit_mode: 'audit',
    })
    ElMessage.success(
      data.status === 'mapped' ? '已提交并完成外部审核（Mock 自动过审）' : '已提交外部审核'
    )
    createVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(channelApiError(e, '提交失败'))
  } finally {
    wizardBusy.value = false
  }
}

async function pause(row) {
  try {
    await ElMessageBox.confirm('确认暂停该映射同步？暂停后抖店新单将被拒收。', '暂停同步', {
      type: 'warning',
    })
    await api.post(`/api/v1/shop/channel-mappings/${row.id}/pause`)
    ElMessage.success('已暂停同步')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '暂停失败')
  }
}

async function resume(row) {
  try {
    await ElMessageBox.confirm('确认恢复同步？恢复后可重新收抖店订单。', '恢复同步')
    await api.post(`/api/v1/shop/channel-mappings/${row.id}/resume`)
    ElMessage.success('已恢复同步')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '恢复失败')
  }
}

async function demoApprove(row) {
  try {
    await api.post(`/api/v1/shop/channel-mappings/${row.id}/external-audit`, { result: 'approved' })
    ElMessage.success('外部审核已通过，商品已挂载')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

async function demoSimulateOrder(row) {
  demoOrderBusyId.value = row.id
  try {
    const { data } = await api.post(`/api/v1/shop/channel-mappings/${row.id}/demo-order`, {
      buyer_mobile: '13700000001',
    })
    demoOrderResult.value = data
    demoOrderVisible.value = true
    ElMessage.success('已模拟抖店下单，请完成领权')
  } catch (e) {
    ElMessage.error(e.message || '模拟下单失败')
  } finally {
    demoOrderBusyId.value = ''
  }
}

function openClaimPage() {
  const url = demoOrderResult.value?.claim_url
  if (!url) return
  window.open(url, '_blank')
}

async function copyClaimLink() {
  const url = demoOrderResult.value?.claim_url
  if (!url) return
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('领权链接已复制')
  } catch {
    ElMessage.info(url)
  }
}

function goOrders() {
  demoOrderVisible.value = false
  router.push('/shop/orders')
}

async function unmount(row) {
  try {
    await ElMessageBox.confirm('确认解除该公域映射？', '解除映射')
    await api.delete(`/api/v1/shop/channel-mappings/${row.id}`)
    ElMessage.success('已解除')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '操作失败')
  }
}

async function openLogs(row) {
  logRow.value = row
  logTab.value = 'all'
  logVisible.value = true
  await loadLogs()
}

function openReason(row) {
  reasonRow.value = row
  reasonVisible.value = true
}

function goEditProduct() {
  if (!reasonRow.value?.product_id) return
  router.push({
    name: 'ShopProductEdit',
    params: { id: reasonRow.value.product_id },
    query: { mode: 'edit' },
  })
}

async function resubmit() {
  if (!reasonRow.value) return
  resubmitting.value = true
  try {
    const { data } = await api.post(
      `/api/v1/shop/channel-mappings/${reasonRow.value.id}/resubmit`,
      { note: '已按驳回原因修改' }
    )
    ElMessage.success(
      data.status === 'mapped' ? '已重新提交并完成外部审核（Mock 自动过审）' : '已重新提交外部审核'
    )
    reasonVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '重新提交失败')
  } finally {
    resubmitting.value = false
  }
}

async function loadLogs() {
  if (!logRow.value) return
  logLoading.value = true
  try {
    const { data } = await api.get(`/api/v1/shop/channel-mappings/${logRow.value.id}/logs`, {
      params: { category: logTab.value },
    })
    logItems.value = data.items || []
  } catch (e) {
    ElMessage.error(e.message || '加载日志失败')
    logItems.value = []
  } finally {
    logLoading.value = false
  }
}

function selectLogTab(key) {
  logTab.value = key
  loadLogs()
}

async function resync() {
  if (!logRow.value) return
  try {
    await api.post(`/api/v1/shop/channel-mappings/${logRow.value.id}/sync`)
    ElMessage.success('已重新同步')
    await loadLogs()
    await load()
  } catch (e) {
    ElMessage.error(e.message || '同步失败')
  }
}

onMounted(async () => {
  await loadSettings()
  await load()
  const prePid = route.query.product_id
  if (prePid && configured.value) {
    const ok = await preloadWizardProduct(String(prePid))
    if (!ok) return
    const picked = selectedProductData.value
    openWizard()
    form.product_id = String(prePid)
    selectedProductData.value = picked
    form.external_title = picked?.name || ''
  }
})

watch(
  () => route.name,
  (name) => {
    if (name === 'ShopChannelMappings') loadSettings()
  }
)

watch(currentId, () => {
  query.page = 1
  load()
})
</script>

<template>
  <div v-loading="loading" class="a14">
    <el-alert
      v-if="!configured"
      type="warning"
      show-icon
      :closable="false"
      style="margin-bottom: 12px"
    >
      <template #title>
        公域对接未完成 — {{ setupHint }}。请先到
        <el-button link type="primary" @click="router.push('/shop/channel-settings')">
          设置 · 公域对接
        </el-button>
        完成配置；新建映射已禁用
      </template>
    </el-alert>

    <el-alert
      v-if="configured && demoToolsEnabled"
      type="info"
      show-icon
      :closable="false"
      class="demo-flow-alert"
    >
      <template #title>本地演示捷径（链路 ①）</template>
      <p class="demo-flow-text">
        ① 审核中的映射点「通过审核」→ ② 已挂载点「模拟下单」→ ③ 打开领权链接绑手机
        <code>13700000001</code> → ④ 商家端「订单」查看待领权单
      </p>
    </el-alert>

    <div class="status-tabs">
      <button
        v-for="t in TABS"
        :key="t.key || 'all'"
        type="button"
        class="status-tab"
        :class="{ on: query.status === t.key }"
        @click="selectTab(t.key)"
      >
        {{ t.label }}
        <span v-if="tabCount(t.key)" class="cnt">{{ tabCount(t.key) }}</span>
      </button>
    </div>

    <div class="toolbar">
      <div class="left">
        <el-input
          v-model="query.q"
          clearable
          placeholder="搜索商品名"
          style="width: 200px"
          @keyup.enter="() => { query.page = 1; load() }"
        />
        <el-select
          v-model="query.status"
          clearable
          placeholder="挂载状态"
          style="width: 130px"
          @change="() => { query.page = 1; load() }"
        >
          <el-option label="已挂载" value="mapped" />
          <el-option label="未挂载" value="unmapped" />
          <el-option label="已阻断" value="blocked" />
          <el-option label="暂停同步" value="paused" />
        </el-select>
        <el-select
          v-model="query.external_audit_status"
          clearable
          placeholder="外部审核"
          style="width: 130px"
          @change="() => { query.page = 1; load() }"
        >
          <el-option label="审核中" value="submitted" />
          <el-option label="已通过" value="approved" />
          <el-option label="被拒" value="rejected" />
        </el-select>
        <el-button :type="advOpen ? 'primary' : 'default'" plain @click="advOpen = !advOpen">
          高级筛选
        </el-button>
      </div>
      <div class="right">
        <el-dropdown trigger="click" @command="exportCsv">
          <el-button :loading="exporting">导出 ▾</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="current">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns }}</el-dropdown-item>
              <el-dropdown-item command="columns">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.visibleColumns }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="openColumnSettings">列设置</el-button>
        <el-button type="primary" :disabled="!configured" @click="openWizard">+ 新建映射</el-button>
      </div>
    </div>

    <div v-if="advOpen" class="adv">
      <div class="adv-t">高级筛选</div>
      <div class="adv-row">
        <el-select v-model="query.path" clearable placeholder="对接路径" style="width: 160px">
          <el-option label="A 官方 API" value="A" />
          <el-option label="B 课程库路径" value="B" />
        </el-select>
        <el-select v-model="query.external_audit_status" clearable placeholder="外部审核" style="width: 130px">
          <el-option label="审核中" value="submitted" />
          <el-option label="已通过" value="approved" />
          <el-option label="被拒" value="rejected" />
        </el-select>
        <el-date-picker
          v-model="query.mapped_from"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="映射起"
          style="width: 140px"
        />
        <span class="sep">—</span>
        <el-date-picker
          v-model="query.mapped_to"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="映射止"
          style="width: 140px"
        />
      </div>
      <div class="adv-row">
        <el-button type="primary" @click="() => { query.page = 1; load() }">查询</el-button>
        <el-button @click="resetAdv">重置</el-button>
        <span class="hint">快捷 Tab 已覆盖已挂载/未挂载/已阻断；路径与映射时间在高级筛选</span>
      </div>
    </div>

    <el-table :data="items" border stripe size="small">
      <template v-for="colKey in visibleKeys" :key="colKey">
      <el-table-column v-if="colKey === 'product_name'" prop="product_name" label="本地商品" min-width="140" />
      <el-table-column
        v-if="colKey === 'product_review_status'"
        prop="product_review_status"
        label="商品审核"
        width="100"
      />
      <el-table-column
        v-if="colKey === 'channel_product_id'"
        prop="channel_product_id"
        label="外部商品 ID"
        width="140"
      />
      <el-table-column v-if="colKey === 'path_label'" prop="path_label" label="路径" width="70" />
      <el-table-column v-if="colKey === 'status_label'" prop="status_label" label="挂载状态" width="100" />
      <el-table-column v-if="colKey === 'external_audit_status'" label="外部审核" width="100">
        <template #default="{ row }">
          {{ row.external_audit_label || row.external_audit_status || '—' }}
        </template>
      </el-table-column>
      <el-table-column v-if="colKey === 'created_at'" label="映射时间" width="140">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'synced_at'" label="最近同步时间" width="140">
        <template #default="{ row }">{{ fmtTime(row.synced_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'channel_label'" prop="channel_label" label="渠道" width="80" />
      <el-table-column v-if="colKey === 'ops'" label="操作" width="demoToolsEnabled ? 300 : 200" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'mapped'">
            <el-button
              v-if="demoToolsEnabled"
              link
              type="success"
              :loading="demoOrderBusyId === row.id"
              @click="demoSimulateOrder(row)"
            >
              模拟下单
            </el-button>
            <el-button link type="warning" @click="pause(row)">暂停</el-button>
            <el-button link type="primary" @click="openLogs(row)">日志</el-button>
            <el-button link type="danger" @click="unmount(row)">解除</el-button>
          </template>
          <template v-else-if="row.status === 'paused'">
            <el-button link type="primary" @click="resume(row)">恢复</el-button>
            <el-button link type="primary" @click="openLogs(row)">日志</el-button>
          </template>
          <template v-else-if="row.status === 'blocked'">
            <el-button link type="danger" @click="openReason(row)">查看原因</el-button>
            <el-button link type="primary" @click="openReason(row)">重新提交</el-button>
          </template>
          <template v-else-if="row.status === 'pending'">
            <el-button v-if="demoToolsEnabled" link type="success" @click="demoApprove(row)">
              通过审核
            </el-button>
            <el-button link type="primary" @click="openLogs(row)">日志</el-button>
          </template>
          <span v-else>—</span>
        </template>
      </el-table-column>
      </template>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="load"
        @size-change="load"
      />
    </div>

    <!-- A14-A 三步向导 -->
    <el-drawer
      v-model="createVisible"
      title="新建抖店商品映射"
      size="680px"
      destroy-on-close
      class="a14-wizard-drawer"
    >
      <div class="steps">
        <span :class="{ on: wizardStep === 1, done: wizardStep > 1 }">1 选品与店</span>
        <span :class="{ on: wizardStep === 2, done: wizardStep > 2 }">2 同步抖店</span>
        <span :class="{ on: wizardStep === 3 }">3 确认提交</span>
      </div>

      <template v-if="wizardStep === 1">
        <div class="step-t">新建抖店商品映射 · 步骤 1/3</div>
        <el-form label-position="top">
          <el-form-item label="本地商品" required>
            <div v-if="selectedProduct" class="picked-product">
              <div class="picked-product__cover">
                <img
                  v-if="selectedProduct.cover_url"
                  :src="authShopFileUrl(selectedProduct.cover_url)"
                  alt=""
                />
                <span v-else>无封面</span>
              </div>
              <div class="picked-product__body">
                <div class="picked-product__name">{{ selectedProduct.name }}</div>
                <div class="picked-product__meta">
                  {{ PRODUCT_TYPE_LABEL[selectedProduct.type] || '商品' }}
                  · {{ fmtMoney(selectedProduct.price_cents) }}
                  <el-tag
                    v-if="selectedProduct.channel_mount_label"
                    size="small"
                    effect="plain"
                    style="margin-left: 6px"
                  >
                    {{ selectedProduct.channel_mount_label }}
                  </el-tag>
                </div>
              </div>
              <el-button link type="primary" @click="clearPickedProduct">更换</el-button>
            </div>
            <ShopProductPickerPanel
              v-show="!selectedProduct"
              ref="productPickerRef"
              v-model="form.product_id"
              :shop-id="currentId || ''"
              @pick="onPickProduct"
            />
            <p v-if="!selectedProduct" class="picker-tip">点击表格行选择商品，支持搜索与分页</p>
          </el-form-item>
          <el-form-item label="对接路径" required>
            <el-select v-model="form.combo" style="width: 100%">
              <el-option
                v-for="o in pathOptions"
                :key="o.value"
                :label="o.label"
                :value="o.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="外部店铺" required>
            <el-input
              :model-value="settings.douyin_shop_id ? `已绑定抖店 ${settings.douyin_shop_id}` : '未绑定'"
              disabled
            />
          </el-form-item>
        </el-form>
        <div class="wiz-ft">
          <el-button type="primary" @click="wizardNext1">下一步</el-button>
          <el-button @click="createVisible = false">取消</el-button>
        </div>
      </template>

      <template v-else-if="wizardStep === 2">
        <div class="step-t">新建抖店商品映射 · 步骤 2/3</div>
        <div class="snap">
          本地商品快照（只读）· {{ selectedProduct?.name || '—' }} ·
          {{ fmtMoney(selectedProduct?.price_cents) }} ·
          {{ { course: '课程', digital: '资料', service: '服务' }[selectedProduct?.type] || '商品' }}
        </div>
        <el-form label-position="top">
          <el-form-item label="抖店展示标题" required>
            <el-input v-model="form.external_title" maxlength="60" show-word-limit />
          </el-form-item>
          <el-form-item label="抖店类目" required>
            <el-select v-model="form.external_category" style="width: 100%">
              <el-option v-for="c in DY_CATEGORIES" :key="c" :label="c" :value="c" />
            </el-select>
          </el-form-item>
          <el-form-item label="抖店售价" required>
            <div class="readonly">{{ fmtMoney(selectedProduct?.price_cents) }}（须与本地售价一致，只读）</div>
          </el-form-item>
          <el-form-item label="主图">
            <div class="cover">
              <img v-if="selectedProduct?.cover_url" :src="authShopFileUrl(selectedProduct.cover_url)" alt="封面" />
              <span v-else>沿用商品封面</span>
            </div>
          </el-form-item>
          <el-form-item label="同步方式">
            <el-select v-model="form.sync_mode" style="width: 100%" disabled>
              <el-option label="在抖店创建新商品" value="create_new" />
            </el-select>
          </el-form-item>
        </el-form>
        <div class="wiz-ft">
          <el-button @click="wizardStep = 1">上一步</el-button>
          <el-button type="primary" :loading="wizardBusy" @click="wizardSyncNext">同步并下一步</el-button>
          <el-button @click="createVisible = false">取消</el-button>
        </div>
      </template>

      <template v-else>
        <div class="step-t">新建抖店商品映射 · 步骤 3/3</div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="本地商品">{{ selectedProduct?.name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="对接路径">{{ pathLabel }} 官方</el-descriptions-item>
          <el-descriptions-item label="外部店铺">抖店 {{ settings.douyin_shop_id }}</el-descriptions-item>
          <el-descriptions-item label="抖店标题 / 类目">
            {{ form.external_title }} · {{ form.external_category }}
          </el-descriptions-item>
          <el-descriptions-item label="外部商品 ID">
            <code>{{ form.channel_product_id || '—' }}</code>（同步后）
          </el-descriptions-item>
          <el-descriptions-item label="提交后状态">进入外部审核，通过后列表见「已挂载」</el-descriptions-item>
        </el-descriptions>
        <p class="hint">提交后进入抖店外部审核；通过 → mapped + approved，列表见「已挂载」。</p>
        <div class="wiz-ft">
          <el-button @click="wizardStep = 2">上一步</el-button>
          <el-button type="primary" :loading="wizardBusy" @click="createMapping">提交映射</el-button>
          <el-button @click="createVisible = false">取消</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- A14-B -->
    <el-drawer
      v-model="reasonVisible"
      :title="`外部审核被拒 · ${reasonRow?.product_name || ''}`"
      size="440px"
      destroy-on-close
    >
      <el-form label-position="top" v-if="reasonRow">
        <el-form-item label="抖店驳回码（只读）">
          <code>{{ reasonRow.mount_blocked_code || '—' }}</code>
        </el-form-item>
        <el-form-item label="原因（只读）">
          <div class="reason-text">{{ reasonRow.mount_blocked_reason || '暂无驳回详情' }}</div>
        </el-form-item>
        <el-form-item label="时间（只读）">
          <span>{{ fmtTime(reasonRow.blocked_at) }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reasonVisible = false">关闭</el-button>
        <el-button @click="goEditProduct">去编辑商品</el-button>
        <el-button type="primary" :loading="resubmitting" @click="resubmit">
          修改并重新提交
        </el-button>
      </template>
    </el-drawer>

    <!-- A14-C -->
    <el-drawer
      v-model="logVisible"
      :title="`公域日志 · ${logRow?.product_name || ''}`"
      size="480px"
      destroy-on-close
    >
      <div v-if="logRow" class="log-meta">
        外部 ID <code>{{ logRow.channel_product_id }}</code> · 路径
        {{ logRow.path_label || 'A' }} ·
        <el-tag size="small">{{ logRow.status_label }}</el-tag>
      </div>
      <div class="log-tabs">
        <button
          v-for="t in LOG_TABS"
          :key="t.key"
          type="button"
          class="log-tab"
          :class="{ on: logTab === t.key }"
          @click="selectLogTab(t.key)"
        >
          {{ t.label }}
        </button>
      </div>
      <div v-loading="logLoading">
        <el-table :data="logItems" size="small" border>
          <el-table-column label="时间" width="130">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="类型" width="80">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ eventBadge(row.event) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="摘要" min-width="160">
            <template #default="{ row }">{{ logSummary(row) }}</template>
          </el-table-column>
        </el-table>
        <div class="log-ft">共 {{ logItems.length }} 条 · 默认近序</div>
      </div>
      <template #footer>
        <el-button @click="logVisible = false">关闭</el-button>
        <el-button type="primary" :disabled="!canResync" @click="resync">重新同步</el-button>
      </template>
    </el-drawer>

    <CrmColumnSettingsDialog
      v-model:visible="colDialog"
      v-model:columns="columnDraft"
      @save="() => { saveColumnSettings(); ElMessage.success('列设置已保存') }"
    />

    <el-dialog v-model="demoOrderVisible" title="模拟抖店下单成功" width="520px">
      <template v-if="demoOrderResult">
        <p class="demo-result-msg">{{ demoOrderResult.message }}</p>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="商品">{{ demoOrderResult.product_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="抖店单号">
            <code>{{ demoOrderResult.external_order_no }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="买家手机">{{ demoOrderResult.buyer_mobile }}</el-descriptions-item>
          <el-descriptions-item label="订单状态">{{ demoOrderResult.order_status || 'claim_pending' }}</el-descriptions-item>
        </el-descriptions>
        <div class="demo-claim-box">
          <div class="demo-claim-label">领权链接（H5）</div>
          <code class="demo-claim-url">{{ demoOrderResult.claim_url }}</code>
        </div>
      </template>
      <template #footer>
        <el-button @click="copyClaimLink">复制领权链接</el-button>
        <el-button type="primary" @click="openClaimPage">打开领权页</el-button>
        <el-button @click="goOrders">查看订单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.status-tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.status-tab {
  border: 0;
  background: transparent;
  padding: 8px 12px;
  cursor: pointer;
  color: var(--el-text-color-secondary);
}
.status-tab.on {
  color: var(--el-color-primary);
  font-weight: 700;
  border-bottom: 2px solid var(--el-color-primary);
}
.cnt {
  margin-left: 4px;
  font-size: 12px;
  opacity: 0.75;
}
.toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.left,
.right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.adv {
  margin-bottom: 12px;
  border: 1px solid #91caff;
  border-radius: 8px;
  padding: 10px 12px;
  background: #f0f7ff;
  font-size: 12px;
}
.adv-t {
  font-weight: 600;
  color: var(--el-color-primary);
  margin-bottom: 8px;
}
.adv-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.sep {
  color: #999;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.log-meta {
  font-size: 12px;
  color: #666;
  margin-bottom: 12px;
}
.log-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid #eee;
  margin-bottom: 12px;
}
.log-tab {
  border: 0;
  background: transparent;
  padding: 8px 10px;
  cursor: pointer;
  font-size: 12px;
  color: #666;
}
.log-tab.on {
  color: var(--el-color-primary);
  font-weight: 600;
  border-bottom: 2px solid var(--el-color-primary);
}
.log-ft {
  margin-top: 8px;
  font-size: 11px;
  color: #999;
}
.reason-text {
  font-size: 13px;
  color: #334155;
  line-height: 1.5;
  white-space: pre-wrap;
}
.steps {
  display: flex;
  gap: 6px;
  margin-bottom: 14px;
  font-size: 11px;
}
.steps span {
  padding: 2px 8px;
  border-radius: 4px;
  background: #f0f0f0;
  color: #999;
}
.steps span.on {
  background: var(--el-color-primary);
  color: #fff;
  font-weight: 700;
}
.steps span.done {
  background: #e6f4ff;
  color: var(--el-color-primary);
}
.step-t {
  font-weight: 600;
  margin-bottom: 12px;
}
.snap {
  font-size: 12px;
  color: #666;
  margin-bottom: 10px;
}
.readonly {
  font-size: 13px;
  color: #334155;
}
.cover {
  min-height: 48px;
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  color: #94a3b8;
  font-size: 12px;
}
.cover img {
  max-height: 80px;
  max-width: 100%;
}
.wiz-ft {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.picked-product {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  margin-bottom: 10px;
  border: 1px solid #91caff;
  border-radius: 8px;
  background: #f0f7ff;
}
.picked-product__cover {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  overflow: hidden;
  background: #e2e8f0;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #94a3b8;
}
.picked-product__cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.picked-product__body {
  flex: 1;
  min-width: 0;
}
.picked-product__name {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.picked-product__meta {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.picker-tip {
  margin: 6px 0 0;
  font-size: 12px;
  color: #94a3b8;
}
.demo-flow-alert {
  margin-bottom: 12px;
}
.demo-flow-text {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}
.demo-flow-text code {
  padding: 0 4px;
  background: #f1f5f9;
  border-radius: 4px;
}
.demo-result-msg {
  margin: 0 0 12px;
  font-size: 13px;
  color: #334155;
}
.demo-claim-box {
  margin-top: 12px;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}
.demo-claim-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}
.demo-claim-url {
  display: block;
  font-size: 11px;
  word-break: break-all;
  color: #0f172a;
}
.hint {
  margin-top: 12px;
  font-size: 12px;
  color: #666;
}
</style>
