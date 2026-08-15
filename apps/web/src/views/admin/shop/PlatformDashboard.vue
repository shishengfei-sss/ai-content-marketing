<script setup>
/**
 * P01 平台经营看板。对照 PRD 06-平台端UI.html #p01 · #p01-cs · #p01-finance · #p01-role-widget-matrix
 * 千人千面：卡片按 widget_order 渲染；null 不展示。GMV/活跃商家只读。
 * 指标卡原文：待审商品 · 待审开通 · 违规待处理 · 待处理续费 · 本月 GMV · 活跃商家
 * 管家：即将到期 · 续费申请中 · 所辖本月 GMV · 活跃客户
 * 财务：待确认批次 · 打款失败 · 本月已结算
 * 下钻：违规待处理 → /admin/shop/moderation?view=open ；结算 → /admin/shop/settlements
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminApi } from '../../../api/client'
import { formatDateTime } from '../../../utils/datetime'

const router = useRouter()
const loading = ref(false)
const exporting = ref(false)
const summary = ref(null)

const GAP_MSG = {}

const widgets = computed(() => summary.value?.widgets || {})
const meta = computed(() => summary.value?.widget_meta || {})
const order = computed(() => summary.value?.widget_order || [])
const table = computed(() => summary.value?.merchant_table || { kind: '', items: [] })
const visibleCards = computed(() =>
  order.value.filter((key) => widgets.value[key] !== null && widgets.value[key] !== undefined),
)

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
      active: '已开通',
      pending: '待审',
      suspended: '已暂停',
      closed: '已关闭',
      expiring_soon: '即将到期',
      expired: '已过期',
      payment_failed: '打款失败',
      paid: '已打款',
      settled: '已结算',
    }[s] || s || '—'
  )
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

async function load() {
  loading.value = true
  try {
    const { data } = await adminApi.getShopAnalyticsSummary()
    summary.value = data
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

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card" data-testid="shop-platform-dashboard">
    <div class="dash-hd">
      <div>
        <h3 class="dash-title">{{ summary?.title || '全站经营看板' }}</h3>
        <p v-if="summary?.subtitle" class="dash-sub">{{ summary.subtitle }}</p>
      </div>
      <el-button type="primary" :loading="exporting" @click="exportDaily">导出日报</el-button>
    </div>

    <el-row :gutter="16" class="dash-stats">
      <el-col v-for="key in visibleCards" :key="key" :xs="24" :sm="12" :md="8" :lg="4">
        <div
          class="stat-card"
          :class="{ 'stat-card--click': meta[key]?.clickable }"
          @click="onCardClick(key)"
        >
          <div class="stat-card__label">
            {{ meta[key]?.label || key }}
            <span v-if="meta[key]?.clickable" class="stat-card__hint">查看</span>
          </div>
          <div
            class="stat-card__value"
            :class="{ 'stat-card__value--primary': meta[key]?.clickable }"
          >
            {{ fmtValue(key, widgets[key]) }}
          </div>
        </div>
      </el-col>
    </el-row>

    <div v-if="table.kind === 'top_gmv_merchants'" class="dash-table">
      <el-table :data="table.items || []" border stripe size="small" @row-click="onMerchantRow">
        <el-table-column prop="name" label="商家" min-width="160" />
        <el-table-column label="本月 GMV" width="140">
          <template #default="{ row }">{{ fmtMoney(row.gmv_month_cents) }}</template>
        </el-table-column>
        <el-table-column v-if="summary?.platform_shop_role !== 'platform_shop_cs'" prop="order_count" label="订单" width="90" />
        <el-table-column v-if="summary?.platform_shop_role === 'platform_shop_cs'" label="套餐状态" width="110">
          <template #default="{ row }">{{ statusLabel(row.plan_status) }}</template>
        </el-table-column>
        <el-table-column v-if="summary?.platform_shop_role === 'platform_shop_cs'" label="权益至" width="120">
          <template #default="{ row }">{{ row.benefits_until || '—' }}</template>
        </el-table-column>
        <el-table-column v-if="summary?.platform_shop_role !== 'platform_shop_cs'" label="状态" width="100">
          <template #default="{ row }">{{ statusLabel(row.onboarding_status) }}</template>
        </el-table-column>
        <el-table-column v-if="summary?.platform_shop_role !== 'platform_shop_cs'" label="最近活跃" width="170">
          <template #default="{ row }">{{ formatDateTime(row.last_active_at) || '—' }}</template>
        </el-table-column>
        <el-table-column v-else label="最近跟进" width="170">
          <template #default="{ row }">{{ formatDateTime(row.last_follow_up_at) || '—' }}</template>
        </el-table-column>
      </el-table>
    </div>

    <div v-else-if="table.kind === 'recent_settlement_batches'" class="dash-table">
      <el-table :data="table.items || []" border stripe size="small" @row-click="onBatchRow">
        <el-table-column prop="batch_no" label="批次号" min-width="140" />
        <el-table-column label="周期" min-width="180">
          <template #default="{ row }">{{ row.period_start }} ~ {{ row.period_end }}</template>
        </el-table-column>
        <el-table-column label="净额" width="140">
          <template #default="{ row }">{{ fmtMoney(row.net_amount_cents) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">{{ statusLabel(row.status) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) || '—' }}</template>
        </el-table-column>
      </el-table>
    </div>
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
  margin-bottom: 20px;
}
.stat-card--click {
  cursor: pointer;
}
.stat-card--click:hover {
  box-shadow: var(--shadow-card-hover, 0 4px 12px rgba(0, 0, 0, 0.08));
}
.stat-card__hint {
  margin-left: 6px;
  font-size: 11px;
  color: var(--color-primary);
}
.dash-table {
  margin-top: 8px;
}
.dash-table :deep(.el-table__row) {
  cursor: pointer;
}
</style>
