<script setup>
/**
 * A09 订单列表。对照 PRD 01-管理端UI.html #a09 / #a09-select-spec
 * 默认列：单号·商品·买家(昵称+脱敏+👁)·金额·渠道·状态·下单时间·操作
 * 列设置可选：支付时间、外部单号（默认开）
 * 写操作弹窗：A09-A/B/C → OrderActionDialogs（#a09a #a09b #a09c）
 * 缺口：站内信/短信本批不接（导出在页内下载，不发站内通知）。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { View } from '@element-plus/icons-vue'
import api from '../../api/client'
import OrderActionDialogs from '../../components/shop/OrderActionDialogs.vue'
import { useCurrentShop } from '../../composables/useCurrentShop'

const router = useRouter()
const route = useRoute()
const actionDialogs = ref(null)
const { currentId } = useCurrentShop()

const loading = ref(false)
const exporting = ref(false)
const exportDialog = ref(false)
const exportTask = ref(null)
const exportScope = ref('当前筛选')
const items = ref([])
const total = ref(0)
const statusCounts = ref({})
const advOpen = ref(false)
const colDialog = ref(false)
const STATUS_LABEL = {
  pending_payment: '待付款',
  paid: '已付款',
  claim_pending: '待领权',
  refunding: '退款中',
  refunded: '已退款',
  closed: '已关闭',
}

const STATUS_TABS = [
  { key: '', label: '全部订单' },
  { key: 'pending_payment', label: '待付款' },
  { key: 'paid', label: '已付款' },
  { key: 'claim_pending', label: '待领权' },
  { key: 'refunding', label: '退款中' },
  { key: 'refunded', label: '已退款' },
]

const COL_STORAGE = 'shop.a09.columns'
const ALL_COLS = [
  { key: 'order_no', label: '单号', locked: true, defaultOn: true },
  { key: 'product_name', label: '商品', locked: true, defaultOn: true },
  { key: 'buyer', label: '买家', locked: true, defaultOn: true },
  { key: 'amount', label: '金额', locked: true, defaultOn: true },
  { key: 'channel', label: '渠道', locked: true, defaultOn: true },
  { key: 'status', label: '状态', locked: true, defaultOn: true },
  { key: 'created_at', label: '下单时间', locked: true, defaultOn: true },
  { key: 'external_order_no', label: '外部单号', locked: false, defaultOn: true },
  { key: 'paid_at', label: '支付时间', locked: false, defaultOn: false },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]

function loadColPrefs() {
  try {
    const raw = localStorage.getItem(COL_STORAGE)
    if (raw) return JSON.parse(raw)
  } catch {
    /* ignore */
  }
  return Object.fromEntries(ALL_COLS.map((c) => [c.key, c.defaultOn]))
}

const colVisible = reactive(loadColPrefs())
const colDraft = reactive({ ...colVisible })

const query = reactive({
  page: 1,
  page_size: 20,
  status: '',
  q: '',
  source: '',
  product_type: '',
  amount_min: undefined,
  amount_max: undefined,
  created_from: '',
  created_to: '',
  external_order_no: '',
})

const revealed = reactive({})

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}

function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 16)
}

function tabCount(key) {
  if (!key) return statusCounts.value.all ?? total.value
  return statusCounts.value[key] ?? 0
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/shop/orders', {
      params: {
        page: query.page,
        page_size: query.page_size,
        shop_id: currentId.value || undefined,
        status: query.status || undefined,
        q: query.q || undefined,
        source: query.source || undefined,
        product_type: query.product_type || undefined,
        amount_min: query.amount_min ?? undefined,
        amount_max: query.amount_max ?? undefined,
        created_from: query.created_from || undefined,
        created_to: query.created_to || undefined,
        external_order_no: query.external_order_no || undefined,
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

function resetAdv() {
  query.product_type = ''
  query.amount_min = undefined
  query.amount_max = undefined
  query.created_from = ''
  query.created_to = ''
  query.external_order_no = ''
  query.page = 1
  load()
}

function listParams(extra = {}) {
  return {
    status: query.status || undefined,
    q: query.q || undefined,
    source: query.source || undefined,
    shop_id: currentId.value || undefined,
    product_type: query.product_type || undefined,
    amount_min: query.amount_min ?? undefined,
    amount_max: query.amount_max ?? undefined,
    created_from: query.created_from || undefined,
    created_to: query.created_to || undefined,
    external_order_no: query.external_order_no || undefined,
    ...extra,
  }
}

function visibleExportColumns() {
  return ALL_COLS.filter((c) => c.key !== 'ops' && colVisible[c.key]).map((c) => c.key)
}

async function exportCsv(mode) {
  exporting.value = true
  try {
    const body = listParams(mode === 'columns' ? { columns: visibleExportColumns() } : {})
    const { data } = await api.post('/api/v1/shop/orders/export', body)
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
    const res = await api.get(`/api/v1/shop/orders/export-tasks/${exportTask.value.id}/file`, {
      responseType: 'blob',
    })
    const blob = new Blob([res.data], { type: 'text/csv; charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportTask.value.file_name || 'shop-orders.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

function openColSettings() {
  Object.assign(colDraft, colVisible)
  colDialog.value = true
}

function saveColSettings() {
  Object.assign(colVisible, colDraft)
  localStorage.setItem(COL_STORAGE, JSON.stringify({ ...colVisible }))
  colDialog.value = false
  ElMessage.success('列设置已保存')
}

async function revealMobile(row) {
  try {
    const { data } = await api.post(`/api/v1/shop/orders/${row.id}/reveal-mobile`)
    revealed[row.id] = data.buyer_mobile
  } catch (e) {
    ElMessage.error(e.message || '无查看权限或操作失败')
  }
}

function openDetail(row) {
  router.push({ name: 'ShopOrderDetail', params: { id: row.id } })
}

function closeOrder(row) {
  actionDialogs.value?.openClose(row)
}

function refund(row) {
  actionDialogs.value?.openRefund(row)
}

function resendNotify(row) {
  actionDialogs.value?.openResend(row)
}

function selectTab(key) {
  query.status = key
  query.page = 1
  load()
}

watch(
  () => query.page_size,
  () => {
    query.page = 1
    load()
  },
)

onMounted(() => {
  if (route.query.status) query.status = String(route.query.status)
  if (route.query.q) query.q = String(route.query.q)
  load()
})

watch(currentId, () => {
  query.page = 1
  load()
})

const visibleCols = computed(() => ALL_COLS.filter((c) => c.locked || colVisible[c.key]))
</script>

<template>
  <div v-loading="loading" class="a09">
    <div class="status-tabs">
      <button
        v-for="t in STATUS_TABS"
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
      <div class="toolbar-left">
        <el-input
          v-model="query.q"
          clearable
          placeholder="单号 / 手机 / 外部单号"
          style="width: 220px"
          @keyup.enter="load"
        />
        <el-select v-model="query.status" clearable placeholder="状态" style="width: 120px" @change="load">
          <el-option v-for="(label, val) in STATUS_LABEL" :key="val" :label="label" :value="val" />
        </el-select>
        <el-select v-model="query.source" clearable placeholder="渠道" style="width: 120px" @change="load">
          <el-option label="微信" value="private" />
          <el-option label="抖店" value="public_douyin" />
          <el-option label="课程库" value="public_course_lib" />
        </el-select>
        <el-button :type="advOpen ? 'primary' : 'default'" @click="advOpen = !advOpen">高级筛选</el-button>
        <el-button type="primary" @click="load">查询</el-button>
      </div>
      <div class="toolbar-right">
        <el-dropdown trigger="click" @command="exportCsv">
          <el-button :loading="exporting">导出 ▾</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="current">当前筛选</el-dropdown-item>
              <el-dropdown-item command="columns">列配置</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="openColSettings">列设置</el-button>
      </div>
    </div>

    <div v-if="advOpen" class="adv">
      <div class="adv-title">高级筛选</div>
      <div class="adv-row">
        <el-input-number v-model="query.amount_min" :min="0" placeholder="金额 ≥" controls-position="right" />
        <el-input-number v-model="query.amount_max" :min="0" placeholder="金额 ≤" controls-position="right" />
        <el-select v-model="query.product_type" clearable placeholder="商品类型" style="width: 120px">
          <el-option label="课程" value="course" />
          <el-option label="资料" value="digital" />
          <el-option label="服务" value="service" />
        </el-select>
        <el-date-picker
          v-model="query.created_from"
          type="datetime"
          placeholder="下单起"
          value-format="YYYY-MM-DDTHH:mm:ss"
        />
        <el-date-picker
          v-model="query.created_to"
          type="datetime"
          placeholder="下单止"
          value-format="YYYY-MM-DDTHH:mm:ss"
        />
        <el-input v-model="query.external_order_no" clearable placeholder="外部单号" style="width: 160px" />
      </div>
      <div class="adv-row">
        <el-button type="primary" @click=";(query.page = 1), load()">查询</el-button>
        <el-button @click="resetAdv">重置</el-button>
        <span class="hint">快捷 Tab 已覆盖待付款/已付款/待领权/退款中/已退款；已关闭与金额/时间在高级筛选</span>
      </div>
    </div>

    <el-table :data="items" border stripe>
      <el-table-column v-if="colVisible.order_no" prop="order_no" label="单号" min-width="150">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">{{ row.order_no }}</el-button>
        </template>
      </el-table-column>
      <el-table-column v-if="colVisible.product_name" prop="product_name" label="商品" min-width="120" />
      <el-table-column v-if="colVisible.buyer" label="买家" min-width="160">
        <template #default="{ row }">
          <div class="buyer-cell">
            <span class="nick">{{ row.buyer_nickname || '—' }}</span>
            <span class="mobile">
              {{ revealed[row.id] || row.buyer_mobile_masked || '—' }}
              <el-button
                v-if="row.buyer_mobile_masked && !revealed[row.id]"
                link
                :icon="View"
                title="查看完整手机号"
                @click="revealMobile(row)"
              />
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="colVisible.amount" label="金额" width="100">
        <template #default="{ row }">{{ fmtMoney(row.amount_cents) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.channel" prop="channel" label="渠道" width="80" />
      <el-table-column v-if="colVisible.status" label="状态" width="100">
        <template #default="{ row }">
          {{ STATUS_LABEL[row.status] || row.status }}
          <el-tag v-if="row.needs_red_flush" type="danger" size="small" style="margin-left: 4px">需红冲</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="colVisible.created_at" label="下单时间" width="140">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.external_order_no" prop="external_order_no" label="外部单号" min-width="120">
        <template #default="{ row }">{{ row.external_order_no || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.paid_at" label="支付时间" width="140">
        <template #default="{ row }">{{ fmtTime(row.paid_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.ops" label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="row.status === 'pending_payment'" link type="warning" @click="closeOrder(row)">
            关闭
          </el-button>
          <el-button v-if="row.status === 'paid'" link type="danger" @click="refund(row)">退款</el-button>
          <el-button v-if="row.status === 'claim_pending'" link type="primary" @click="resendNotify(row)">
            重发短信
          </el-button>
        </template>
      </el-table-column>
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

    <el-dialog v-model="colDialog" title="列设置" width="400px">
      <div v-for="c in ALL_COLS" :key="c.key" class="col-row">
        <el-checkbox v-model="colDraft[c.key]" :disabled="c.locked">{{ c.label }}</el-checkbox>
        <span v-if="c.locked" class="locked">锁定</span>
      </div>
      <template #footer>
        <el-button @click="colDialog = false">取消</el-button>
        <el-button type="primary" @click="saveColSettings">保存</el-button>
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

    <OrderActionDialogs ref="actionDialogs" @done="load" />
  </div>
</template>

<style scoped>
.a09 {
  padding-bottom: 16px;
}
.status-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  border-bottom: 1px solid var(--el-border-color);
  margin-bottom: 12px;
}
.status-tab {
  border: 0;
  background: transparent;
  padding: 8px 14px;
  cursor: pointer;
  color: #666;
  font-size: 13px;
}
.status-tab.on {
  color: #1677ff;
  font-weight: 700;
  border-bottom: 2px solid #1677ff;
}
.cnt {
  margin-left: 4px;
  font-size: 12px;
  color: #999;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.adv {
  border: 1px solid #91caff;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
  background: #f0f7ff;
}
.adv-title {
  font-weight: 600;
  color: #1677ff;
  margin-bottom: 8px;
  font-size: 12px;
}
.adv-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.hint {
  color: #666;
  font-size: 11px;
}
.buyer-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}
.nick {
  font-weight: 600;
}
.mobile {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: #666;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.col-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.locked {
  font-size: 11px;
  color: #999;
}
</style>
