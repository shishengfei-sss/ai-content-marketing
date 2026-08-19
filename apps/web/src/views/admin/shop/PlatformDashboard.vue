<script setup>
/**
 * P01 平台经营看板。对照 PRD 06-平台端UI.html #p01 · #p01-cs · #p01-finance · #p01-role-widget-matrix
 * 千人千面：卡片按 widget_order 渲染；null 不展示。GMV/活跃商家只读。
 * 指标卡原文：待审商品 · 待审开通 · 违规待处理 · 待处理续费 · 本月 GMV · 活跃商家
 * 管家：即将到期 · 续费申请中 · 所辖本月 GMV · 活跃客户
 * 财务：待确认批次 · 打款失败 · 本月已结算
 * 下钻：违规待处理 → /admin/shop/moderation?view=open ；结算 → /admin/shop/settlements
 * 趋势：GET /admin/shop/analytics/trends（PRD §8.14.1），与 A01 / 工作台同壳。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowRight,
  CircleCheck,
  CircleCloseFilled,
  Clock,
  Coin,
  Document,
  Goods,
  Shop,
  Ticket,
  User,
  Wallet,
  WarningFilled,
} from '@element-plus/icons-vue'
import { adminApi } from '../../../api/client'
import { formatDateTime, parseApiDateTime } from '../../../utils/datetime'

const router = useRouter()
const loading = ref(false)
const exporting = ref(false)
const summary = ref(null)
const trends = ref(null)
const chartRange = ref('7d')

const GAP_MSG = {}

const CARD_UI = {
  pending_product_reviews: { tone: 'primary', icon: Goods },
  pending_onboarding: { tone: 'primary', icon: User },
  open_moderation_cases: { tone: 'warning', icon: WarningFilled },
  pending_renewals: { tone: 'danger', icon: Ticket },
  gmv_month_cents: { tone: 'money', icon: Coin },
  active_merchants: { tone: 'info', icon: Shop },
  expiring_soon_merchants: { tone: 'warning', icon: Clock },
  my_pending_renewal_requests: { tone: 'primary', icon: Document },
  settlement_batches_pending: { tone: 'warning', icon: Wallet },
  settlement_batches_failed: { tone: 'danger', icon: CircleCloseFilled },
  settled_month_cents: { tone: 'success', icon: CircleCheck },
}

const widgets = computed(() => summary.value?.widgets || {})
const meta = computed(() => summary.value?.widget_meta || {})
const order = computed(() => summary.value?.widget_order || [])
const table = computed(() => summary.value?.merchant_table || { kind: '', items: [] })
const visibleCards = computed(() =>
  order.value.filter((key) => widgets.value[key] !== null && widgets.value[key] !== undefined),
)
const isCs = computed(() => summary.value?.platform_shop_role === 'platform_shop_cs')
const tableTitle = computed(() => {
  if (table.value.kind === 'recent_settlement_batches') return '最近结算批次'
  return isCs.value ? '我的客户' : '本月 GMV 商家'
})
const tableMorePath = computed(() =>
  table.value.kind === 'recent_settlement_batches' ? '/admin/shop/settlements' : '/admin/shop/merchants',
)
const trendPoints = computed(() => trends.value?.points || [])
const trendMax = computed(() => Math.max(1, ...trendPoints.value.map((p) => p.gmv_cents || 0)))

function cardUi(key) {
  return CARD_UI[key] || { tone: 'info', icon: Shop }
}

function fmtMoney(cents) {
  return `¥${((Number(cents) || 0) / 100).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function fmtValue(key, val) {
  const spec = meta.value[key] || {}
  if (spec.format === 'money') return fmtMoney(val)
  return String(val ?? 0)
}

function statusLabel(s) {
  return (
    {
      active: '正常',
      pending: '审核中',
      reviewing: '审核中',
      suspended: '已暂停',
      closed: '已清退',
      expiring_soon: '即将到期',
      expired: '已到期',
      payment_failed: '打款失败',
      paid: '已打款',
      settled: '已结算',
    }[s] || s || '—'
  )
}

function statusTagType(s) {
  return (
    {
      active: 'success',
      pending: 'warning',
      reviewing: 'warning',
      suspended: 'warning',
      closed: 'info',
      expiring_soon: 'warning',
      expired: 'info',
      payment_failed: 'danger',
      paid: 'success',
      settled: 'success',
    }[s] || 'info'
  )
}

function formatRelative(value) {
  const d = parseApiDateTime(value)
  if (!d) return '—'
  const diff = Date.now() - d.getTime()
  const min = 60 * 1000
  const hour = 60 * min
  const day = 24 * hour
  if (diff < 0) return formatDateTime(value, { withSeconds: false })
  if (diff < min) return '刚刚'
  if (diff < hour) return `${Math.floor(diff / min)} 分钟前`
  if (diff < day) return `${Math.floor(diff / hour)} 小时前`
  if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`
  return formatDateTime(value, { withSeconds: false })
}

function barHeight(cents) {
  return `${Math.max(4, Math.round(((Number(cents) || 0) / trendMax.value) * 100))}%`
}

function dayLabel(iso) {
  return String(iso || '').slice(5)
}

function onCardClick(key) {
  const spec = meta.value[key] || {}
  if (!spec.clickable) return
  if (spec.gap && GAP_MSG[spec.gap]) {
    ElMessage.info(GAP_MSG[spec.gap])
    return
  }
  if (spec.href) router.push(spec.href)
}

function onMerchantRow(row) {
  if (!row?.tenant_id) return
  router.push(`/admin/shop/merchants/${row.tenant_id}`)
}

function onBatchRow(row) {
  if (row?.id) router.push(`/admin/shop/settlements?id=${row.id}`)
  else router.push('/admin/shop/settlements')
}

async function loadTrends() {
  try {
    const { data } = await adminApi.getShopAnalyticsTrends({ range: chartRange.value })
    trends.value = data
  } catch {
    trends.value = { points: [] }
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await adminApi.getShopAnalyticsSummary()
    summary.value = data
    await loadTrends()
  } catch (e) {
    ElMessage.error(e.message || '看板加载失败')
  } finally {
    loading.value = false
  }
}

async function exportDaily() {
  exporting.value = true
  try {
    const today = new Date()
    const date = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
    const { data } = await adminApi.exportShopAnalyticsDaily({ date })
    const blob = data instanceof Blob ? data : new Blob([data])
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `shop-platform-daily-${date}.csv`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出日报')
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

watch(chartRange, loadTrends)
onMounted(load)
</script>

<template>
  <div v-loading="loading" class="dash" data-testid="shop-platform-dashboard">
    <div class="dash-hd">
      <div>
        <h3 class="dash-title">{{ summary?.title || '全站经营看板' }}</h3>
        <p v-if="summary?.subtitle" class="dash-sub">{{ summary.subtitle }}</p>
      </div>
      <el-button type="primary" :loading="exporting" @click="exportDaily">导出日报</el-button>
    </div>

    <div class="dash-stats">
      <div
        v-for="key in visibleCards"
        :key="key"
        class="stat-card dash-card"
        :class="[
          `dash-card--${cardUi(key).tone}`,
          { 'dash-card--click': meta[key]?.clickable },
        ]"
        :role="meta[key]?.clickable ? 'link' : undefined"
        :tabindex="meta[key]?.clickable ? 0 : undefined"
        @click="onCardClick(key)"
        @keydown.enter="onCardClick(key)"
      >
        <div class="dash-card__icon" aria-hidden="true">
          <el-icon :size="18"><component :is="cardUi(key).icon" /></el-icon>
        </div>
        <div class="dash-card__body">
          <div class="stat-card__label dash-card__label">
            {{ meta[key]?.label || key }}
            <el-icon v-if="meta[key]?.clickable" class="dash-card__go"><ArrowRight /></el-icon>
          </div>
          <div
            class="stat-card__value dash-card__value"
            :class="{ 'stat-card__value--primary': meta[key]?.clickable && cardUi(key).tone === 'primary' }"
          >
            {{ fmtValue(key, widgets[key]) }}
          </div>
        </div>
      </div>
    </div>

    <el-row :gutter="16" class="dash-body">
      <el-col :xs="24" :lg="16">
        <div class="page-card dash-panel">
          <div class="dash-panel__hd">
            <span class="dash-panel__title">{{ tableTitle }}</span>
            <el-button type="primary" link @click="router.push(tableMorePath)">查看全部</el-button>
          </div>

          <div v-if="table.kind === 'top_gmv_merchants'" class="crm-list-table-wrap">
            <el-table
              class="crm-list-table"
              :data="table.items || []"
              stripe
              empty-text="暂无商家"
              @row-click="onMerchantRow"
            >
              <el-table-column prop="name" label="商家" min-width="160" show-overflow-tooltip />
              <el-table-column label="本月 GMV" width="140">
                <template #default="{ row }">
                  <span class="dash-money">{{ fmtMoney(row.gmv_month_cents) }}</span>
                </template>
              </el-table-column>
              <el-table-column v-if="!isCs" prop="order_count" label="订单" width="90" />
              <el-table-column v-if="isCs" label="套餐状态" width="110">
                <template #default="{ row }">
                  <el-tag size="small" :type="statusTagType(row.plan_status)">
                    {{ statusLabel(row.plan_status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column v-if="isCs" label="权益至" width="120">
                <template #default="{ row }">{{ row.benefits_until || '—' }}</template>
              </el-table-column>
              <el-table-column v-if="!isCs" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag size="small" :type="statusTagType(row.onboarding_status)">
                    {{ statusLabel(row.onboarding_status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column v-if="!isCs" label="最近活跃" min-width="140">
                <template #default="{ row }">
                  <span :title="formatDateTime(row.last_active_at)">
                    {{ formatRelative(row.last_active_at) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column v-else label="最近跟进" min-width="140">
                <template #default="{ row }">
                  <span :title="formatDateTime(row.last_follow_up_at)">
                    {{ formatRelative(row.last_follow_up_at) }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div v-else-if="table.kind === 'recent_settlement_batches'" class="crm-list-table-wrap">
            <el-table
              class="crm-list-table"
              :data="table.items || []"
              stripe
              empty-text="暂无结算批次"
              @row-click="onBatchRow"
            >
              <el-table-column prop="batch_no" label="批次号" min-width="140" />
              <el-table-column label="周期" min-width="180">
                <template #default="{ row }">{{ row.period_start }} ~ {{ row.period_end }}</template>
              </el-table-column>
              <el-table-column label="净额" width="140">
                <template #default="{ row }">
                  <span class="dash-money">{{ fmtMoney(row.net_amount_cents) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag size="small" :type="statusTagType(row.status)">
                    {{ statusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="创建时间" min-width="140">
                <template #default="{ row }">
                  <span :title="formatDateTime(row.created_at)">{{ formatRelative(row.created_at) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :lg="8">
        <div class="page-card dash-panel dash-chart">
          <div class="dash-panel__hd">
            <span class="dash-panel__title">GMV 趋势</span>
            <el-radio-group v-model="chartRange" size="small">
              <el-radio-button value="7d">近7天</el-radio-button>
              <el-radio-button value="30d">近30天</el-radio-button>
            </el-radio-group>
          </div>
          <div v-if="trendPoints.length" class="dash-bars" :class="{ 'dash-bars--dense': chartRange === '30d' }">
            <div v-for="p in trendPoints" :key="p.date" class="dash-bar">
              <i
                :style="{ height: barHeight(p.gmv_cents) }"
                :title="`${p.date} ${fmtMoney(p.gmv_cents)} · ${p.order_count || 0} 单`"
              />
              <span v-if="chartRange === '7d'">{{ dayLabel(p.date) }}</span>
            </div>
          </div>
          <div v-else class="dash-chart__empty">暂无成交</div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dash-hd {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.dash-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.dash-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.dash-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.dash-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border: 1px solid transparent;
  transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;
}
.dash-card__icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: #f0f5ff;
  color: var(--color-primary);
}
.dash-card__body {
  min-width: 0;
  flex: 1;
}
.dash-card__label {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 6px;
}
.dash-card__go {
  font-size: 12px;
  color: var(--color-primary);
  opacity: 0.7;
}
.dash-card__value {
  font-size: 22px;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.dash-card--click {
  cursor: pointer;
}
.dash-card--click:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(22, 119, 255, 0.12);
  border-color: #91caff;
}
.dash-card--primary .dash-card__icon {
  background: #f0f5ff;
  color: var(--color-primary);
}
.dash-card--warning .dash-card__icon {
  background: #fff7e6;
  color: #d46b08;
}
.dash-card--warning .dash-card__value {
  color: #d46b08;
}
.dash-card--danger .dash-card__icon {
  background: #fff1f0;
  color: #cf1322;
}
.dash-card--danger .dash-card__value {
  color: #cf1322;
}
.dash-card--success .dash-card__icon {
  background: #f6ffed;
  color: #389e0d;
}
.dash-card--money .dash-card__icon,
.dash-card--info .dash-card__icon {
  background: #f5f5f5;
  color: #595959;
}
.dash-body {
  margin-bottom: 8px;
}
.dash-panel {
  height: 100%;
}
.dash-panel__hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.dash-panel__title {
  font-size: 15px;
  font-weight: 600;
}
.dash-panel :deep(.el-table__row) {
  cursor: pointer;
}
.dash-money {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.dash-chart {
  min-height: 280px;
  display: flex;
  flex-direction: column;
}
.dash-bars {
  flex: 1;
  display: flex;
  align-items: stretch;
  gap: 8px;
  min-height: 200px;
  padding-top: 8px;
}
.dash-bars--dense {
  gap: 3px;
}
.dash-bar {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}
.dash-bar i {
  display: block;
  width: 100%;
  max-width: 28px;
  min-height: 4px;
  margin: 0 auto;
  background: linear-gradient(180deg, #4096ff 0%, #1677ff 100%);
  border-radius: 4px 4px 2px 2px;
  opacity: 0.88;
}
.dash-bar span {
  font-size: 11px;
  color: var(--color-text-muted, #999);
  white-space: nowrap;
}
.dash-chart__empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  font-size: 13px;
  color: var(--color-text-muted, #999);
}
@media (max-width: 1200px) {
  .dash-body .el-col + .el-col {
    margin-top: 16px;
  }
}
</style>
