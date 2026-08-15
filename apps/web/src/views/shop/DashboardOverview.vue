<script setup>
/**
 * A01 交易看板。对照 PRD 01-管理端UI.html #a01 · #a01-select-spec
 * 指标卡可下钻 A08/A13/A09/A02；最近订单对齐 A09（无列设置）。
 * 当前店铺在顶栏切换，本页按 shop_id 拉数。
 * 缺口：站内信本批不接（恢复提醒里导出积压在页内下载）。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import OrderActionDialogs from '../../components/shop/OrderActionDialogs.vue'
import { hasPermission } from '../../config/permissions'
import { useAuthStore } from '../../stores/auth'
import { useCurrentShop } from '../../composables/useCurrentShop'

const RESUME_DISMISS_KEY = 'shop.a01.resume_dismissed'

const router = useRouter()
const auth = useAuthStore()
const actionDialogs = ref(null)
const { currentId } = useCurrentShop()

const loading = ref(false)
const summary = ref(null)
const trends = ref(null)
const orders = ref([])
const orderTotal = ref(0)
const customRange = ref([])
const resumeDismissed = ref(localStorage.getItem(RESUME_DISMISS_KEY) === '1')
const exportDialog = ref(false)
const exportTask = ref(null)

const RANGE_BTNS = [
  { key: 'today', label: '今日' },
  { key: '7d', label: '近7日' },
  { key: '30d', label: '近30日' },
  { key: 'custom', label: '自定义' },
]

const STATUS_LABEL = {
  pending_payment: '待付款',
  paid: '已付款',
  claim_pending: '待领权',
  refunding: '退款中',
  refunded: '已退款',
  closed: '已关闭',
}

const query = reactive({
  range: 'today',
  shop_id: currentId.value || '',
  q: '',
  source: '',
  status: '',
  page: 1,
  page_size: 10,
  sort_by: '',
  sort_dir: '',
})

const canViewOrder = computed(() => hasPermission(auth.permissions, 'shop.order.view'))
const canClose = computed(() => hasPermission(auth.permissions, 'shop.order.close'))
const canRefund = computed(() => hasPermission(auth.permissions, 'shop.order.refund'))
const canResend = computed(() => hasPermission(auth.permissions, 'shop.order.resend_notify'))
const canExport = computed(() => hasPermission(auth.permissions, 'shop.order.export'))

const resume = computed(() => summary.value?.resume)
const showResume = computed(
  () => Boolean(resume.value?.show) && !resumeDismissed.value,
)

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}
function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 16)
}
function rangeParams() {
  const p = { range: query.range, shop_id: query.shop_id || undefined }
  if (query.range === 'custom' && customRange.value?.length === 2) {
    p.date_from = customRange.value[0]
    p.date_to = customRange.value[1]
  }
  return p
}

async function loadAll(keepPage) {
  if (query.range === 'custom' && (!customRange.value || customRange.value.length !== 2)) {
    ElMessage.warning('请选择自定义起止日期')
    return
  }
  if (!keepPage) query.page = 1
  loading.value = true
  try {
    const params = rangeParams()
    const [s, t] = await Promise.all([
      api.get('/api/v1/shop/analytics/summary', { params }),
      api.get('/api/v1/shop/analytics/trends', { params }),
    ])
    summary.value = s.data
    trends.value = t.data
    await loadOrders()
  } catch (e) {
    ElMessage.error(e.message || '看板加载失败')
  } finally {
    loading.value = false
  }
}

async function loadOrders() {
  const { data } = await api.get('/api/v1/shop/analytics/recent-orders', {
    params: {
      shop_id: query.shop_id || undefined,
      q: query.q || undefined,
      source: query.source || undefined,
      status: query.status || undefined,
      page: query.page,
      page_size: query.page_size,
      sort_by: query.sort_by || undefined,
      sort_dir: query.sort_dir || undefined,
    },
  })
  orders.value = data.items || []
  orderTotal.value = data.total || 0
}

function setRange(key) {
  query.range = key
  if (key !== 'custom') loadAll()
}

watch(currentId, (id) => {
  query.shop_id = id || ''
  loadAll()
})

function toggleSort(col) {
  if (query.sort_by === col) {
    query.sort_dir = query.sort_dir === 'asc' ? 'desc' : 'asc'
  } else {
    query.sort_by = col
    query.sort_dir = 'desc'
  }
  query.page = 1
  loadOrders()
}

function resetOrders() {
  query.q = ''
  query.source = ''
  query.status = ''
  query.sort_by = ''
  query.sort_dir = ''
  query.page = 1
  loadOrders()
}

function drill(kind) {
  if (kind === 'verify') router.push('/shop/verifications')
  else if (kind === 'invoice') router.push({ path: '/shop/invoices', query: { status: 'submitted' } })
  else if (kind === 'claim') router.push({ path: '/shop/orders', query: { status: 'claim_pending' } })
  else if (kind === 'refund') router.push({ path: '/shop/orders', query: { status: 'refunding' } })
  else if (kind === 'offsale') router.push({ path: '/shop/products', query: { status: 'off_sale' } })
}

function openDetail(row) {
  if (!canViewOrder.value) {
    ElMessage.error('无订单查看权限')
    return
  }
  router.push({ name: 'ShopOrderDetail', params: { id: row.id } })
}

function barMax() {
  const pts = trends.value?.daily || []
  return Math.max(1, ...pts.map((p) => p.gmv_cents || 0))
}

function dismissResume() {
  resumeDismissed.value = true
  localStorage.setItem(RESUME_DISMISS_KEY, '1')
}

async function exportBacklog() {
  try {
    const { data } = await api.post('/api/v1/shop/orders/export', { status: 'claim_pending' })
    exportTask.value = data
    exportDialog.value = true
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  }
}

async function downloadBacklogFile() {
  if (!exportTask.value?.id) return
  try {
    const res = await api.get(`/api/v1/shop/orders/export-tasks/${exportTask.value.id}/file`, {
      responseType: 'blob',
    })
    const blob = new Blob([res.data], { type: 'text/csv; charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportTask.value.file_name || 'shop-backlog.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

onMounted(loadAll)
</script>

<template>
  <div v-loading="loading" class="page-card a01" data-testid="shop-dashboard-container">
    <div class="hd">
      <h3>交易看板</h3>
    </div>

    <el-alert
      v-if="showResume"
      class="resume"
      type="warning"
      show-icon
      :closable="true"
      @close="dismissResume"
    >
      <template #title>
        商家账号已恢复，请前往
        <el-button link type="primary" @click="router.push('/shop/stores')">店铺管理</el-button>
        恢复店铺营业；您有
        <b>{{ resume.pending_order_count }}</b>
        笔订单待处理 ·
        <el-button link type="primary" @click="router.push('/shop/orders')">去订单列表</el-button>
        <el-button v-if="canExport" link type="primary" @click="exportBacklog">导出积压 CSV</el-button>
      </template>
    </el-alert>

    <div class="toolbar">
      <div class="range" data-testid="select-time-range">
        <el-button
          v-for="b in RANGE_BTNS"
          :key="b.key"
          :type="query.range === b.key ? 'primary' : 'default'"
          @click="setRange(b.key)"
        >
          {{ b.label }}
        </el-button>
        <el-date-picker
          v-if="query.range === 'custom'"
          v-model="customRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始"
          end-placeholder="结束"
          @change="loadAll"
        />
      </div>
      <div class="toolbar-right">
        <el-button @click="loadAll(true)">刷新</el-button>
      </div>
    </div>

    <div class="stats">
      <div class="stat" data-testid="card-today-revenue">
        <div class="v">{{ fmtMoney(summary?.gmv_cents) }}</div>
        <div class="l">成交额</div>
      </div>
      <div class="stat" data-testid="card-today-orders">
        <div class="v">{{ summary?.order_count ?? 0 }}</div>
        <div class="l">订单数</div>
      </div>
      <div class="stat">
        <div class="v">{{ summary?.payment_conversion == null ? '—' : `${summary.payment_conversion}%` }}</div>
        <div class="l">支付转化*（可隐）</div>
      </div>
      <button type="button" class="stat click warn" @click="drill('refund')">
        <div class="v">{{ summary?.pending_refunds ?? 0 }}</div>
        <div class="l">待处理退款</div>
      </button>
    </div>
    <div class="stats">
      <button type="button" class="stat click warn" data-testid="card-pending-verification" @click="drill('verify')">
        <div class="v">{{ summary?.pending_verify ?? 0 }}</div>
        <div class="l">待核销 →</div>
      </button>
      <button type="button" class="stat click warn" @click="drill('invoice')">
        <div class="v">{{ summary?.pending_invoices ?? 0 }}</div>
        <div class="l">待开票 →</div>
      </button>
      <button type="button" class="stat click warn" @click="drill('claim')">
        <div class="v">{{ summary?.pending_claims ?? 0 }}</div>
        <div class="l">待领权公域单 →</div>
      </button>
      <button type="button" class="stat click" @click="drill('offsale')">
        <div class="v">{{ summary?.off_sale_products ?? 0 }}</div>
        <div class="l">下架商品数</div>
      </button>
    </div>

    <div class="charts">
      <div class="chart" data-testid="chart-revenue-trend">
        <div class="t">成交额按日</div>
        <div class="bars">
          <i
            v-for="p in trends?.daily || []"
            :key="p.date"
            :style="{ height: `${Math.round(((p.gmv_cents || 0) / barMax()) * 100)}%` }"
            :title="`${p.date} ${fmtMoney(p.gmv_cents)}`"
          />
        </div>
        <div v-if="!(trends?.daily || []).length" class="empty">暂无成交</div>
      </div>
      <div class="chart">
        <div class="t">品类占比</div>
        <div class="shares">
          <div v-for="s in trends?.by_category || []" :key="s.key" class="share">
            <span>{{ s.label }}</span>
            <span>{{ s.percent }}%</span>
          </div>
          <div v-if="!(trends?.by_category || []).length" class="empty">暂无</div>
        </div>
      </div>
      <div class="chart">
        <div class="t">渠道占比</div>
        <div class="shares">
          <div v-for="s in trends?.by_channel || []" :key="s.key" class="share">
            <span>{{ s.label }}</span>
            <span>{{ s.percent }}%</span>
          </div>
          <div v-if="!(trends?.by_channel || []).length" class="empty">暂无</div>
        </div>
      </div>
    </div>

    <div class="recent">
      <div class="tbl-head">
        <h4>最近订单</h4>
        <div class="tbl-filters">
          <el-input
            v-model="query.q"
            clearable
            placeholder="单号 / 商品 / 买家"
            style="width: 200px"
            @keyup.enter=";(query.page = 1), loadOrders()"
          />
          <el-select v-model="query.source" clearable placeholder="渠道：全部" style="width: 130px" @change=";(query.page = 1), loadOrders()">
            <el-option label="微信" value="private" />
            <el-option label="抖店" value="public_douyin" />
            <el-option label="其它" value="public_course_lib" />
          </el-select>
          <el-select v-model="query.status" clearable placeholder="状态：全部" style="width: 130px" @change=";(query.page = 1), loadOrders()">
            <el-option v-for="(label, val) in STATUS_LABEL" :key="val" :label="label" :value="val" />
          </el-select>
          <el-button @click="resetOrders">重置</el-button>
        </div>
      </div>
      <el-table :data="orders" border stripe @sort-change="() => {}">
        <el-table-column label="单号" min-width="150">
          <template #header>
            <button type="button" class="sort" @click="toggleSort('no')">单号 ↕</button>
          </template>
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">{{ row.order_no }}</el-button>
          </template>
        </el-table-column>
        <el-table-column label="商品" min-width="120">
          <template #header>
            <button type="button" class="sort" @click="toggleSort('product')">商品 ↕</button>
          </template>
          <template #default="{ row }">{{ row.product_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="买家" min-width="120">
          <template #header>
            <button type="button" class="sort" @click="toggleSort('buyer')">买家 ↕</button>
          </template>
          <template #default="{ row }">{{ row.buyer_nickname || row.buyer_mobile_masked || '—' }}</template>
        </el-table-column>
        <el-table-column label="金额" width="100">
          <template #header>
            <button type="button" class="sort" @click="toggleSort('amount')">金额 ↕</button>
          </template>
          <template #default="{ row }">{{ fmtMoney(row.amount_cents) }}</template>
        </el-table-column>
        <el-table-column label="渠道" width="80">
          <template #header>
            <button type="button" class="sort" @click="toggleSort('channel')">渠道 ↕</button>
          </template>
          <template #default="{ row }">{{ row.channel || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #header>
            <button type="button" class="sort" @click="toggleSort('status')">状态 ↕</button>
          </template>
          <template #default="{ row }">{{ STATUS_LABEL[row.status] || row.status }}</template>
        </el-table-column>
        <el-table-column label="下单时间" width="150">
          <template #header>
            <button type="button" class="sort" @click="toggleSort('ordered_at')">下单时间 ↕</button>
          </template>
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canViewOrder" link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button
              v-if="canClose && row.status === 'pending_payment'"
              link
              type="warning"
              @click="actionDialogs?.openClose(row)"
            >
              关闭
            </el-button>
            <el-button
              v-if="canRefund && row.status === 'paid'"
              link
              type="danger"
              @click="actionDialogs?.openRefund(row)"
            >
              退款
            </el-button>
            <el-button
              v-if="canResend && row.status === 'claim_pending'"
              link
              type="primary"
              @click="actionDialogs?.openResend(row)"
            >
              重发短信
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="orderTotal"
          :page-sizes="[5, 10, 20]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadOrders"
          @size-change=";(query.page = 1), loadOrders()"
        />
      </div>
    </div>

    <el-dialog v-model="exportDialog" title="导出任务" width="420px">
      <el-form v-if="exportTask" label-width="100px">
        <el-form-item label="范围">待领权公域单</el-form-item>
        <el-form-item label="条数">{{ exportTask.row_count ?? 0 }} 条</el-form-item>
        <el-form-item label="状态">{{ exportTask.status === 'done' ? '已完成' : (exportTask.status || '—') }}</el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :disabled="exportTask?.status !== 'done'" @click="downloadBacklogFile">
          下载
        </el-button>
        <el-button @click="exportDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <OrderActionDialogs ref="actionDialogs" @done="loadOrders" />
  </div>
</template>

<style scoped>
.a01 .hd h3 {
  margin: 0 0 12px;
  font-size: 18px;
}
.resume {
  margin-bottom: 12px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.range,
.toolbar-right,
.tbl-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 10px;
}
.stat {
  border: 1px solid var(--el-border-color, #e5e7eb);
  border-radius: 8px;
  padding: 12px 14px;
  background: #fff;
  text-align: left;
}
.stat.click {
  cursor: pointer;
}
.stat.click:hover {
  border-color: var(--el-color-primary);
}
.stat.warn .v {
  color: #d46b08;
}
.stat .v {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.3;
}
.stat .l {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}
.charts {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 10px;
  margin-bottom: 16px;
}
.chart {
  border: 1px solid var(--el-border-color, #e5e7eb);
  border-radius: 8px;
  padding: 12px;
  min-height: 140px;
  background: #fff;
}
.chart .t {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.bars {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 90px;
}
.bars i {
  flex: 1;
  min-height: 2px;
  background: var(--el-color-primary, #1677ff);
  border-radius: 2px 2px 0 0;
  opacity: 0.75;
}
.shares {
  font-size: 12px;
  color: #666;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.share {
  display: flex;
  justify-content: space-between;
}
.empty {
  font-size: 12px;
  color: #999;
}
.tbl-head {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.tbl-head h4 {
  margin: 0;
  font-size: 15px;
}
.sort {
  border: 0;
  background: none;
  cursor: pointer;
  padding: 0;
  font: inherit;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
@media (max-width: 960px) {
  .stats,
  .charts {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
