<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { crmApi } from '../api/client'

const loading = ref(false)
const report = ref(null)

const paths = computed(() => report.value?.paths || [])
const owners = computed(() => report.value?.owners || [])
const agingBuckets = computed(() => {
  const b = report.value?.aging?.buckets || {}
  return [
    { key: 'current', label: '未逾期', value: b.current || 0 },
    { key: 'd30', label: '1～30 天', value: b.d30 || 0 },
    { key: 'd60', label: '31～60 天', value: b.d60 || 0 },
    { key: 'd90plus', label: '90+ 天', value: b.d90plus || 0 },
  ]
})

function money(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}

async function load() {
  loading.value = true
  try {
    const { data } = await crmApi.tradeReport()
    report.value = data
  } catch (e) {
    ElMessage.error(e.message || '加载交易报表失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card trade-report">
    <div class="trade-report__header">
      <div>
        <h2 class="trade-report__title">交易报表</h2>
        <p class="trade-report__desc">订单转化路径、回款率、应收账龄与负责人业绩</p>
      </div>
      <el-button @click="load">刷新</el-button>
    </div>

    <div v-if="report" class="trade-report__summary">
      <div class="metric">
        <span class="metric__label">商机总数</span>
        <strong>{{ report.deal_total }}</strong>
      </div>
      <div class="metric">
        <span class="metric__label">赢单数</span>
        <strong>{{ report.won_deal_count }}</strong>
      </div>
      <div class="metric">
        <span class="metric__label">有效订单</span>
        <strong>{{ report.order_count }}</strong>
      </div>
      <div class="metric">
        <span class="metric__label">商机→订单转化</span>
        <strong>{{ report.deal_to_order_rate }}%</strong>
      </div>
      <div class="metric">
        <span class="metric__label">回款率</span>
        <strong>{{ report.payment_rate }}%</strong>
      </div>
      <div class="metric">
        <span class="metric__label">应收合计</span>
        <strong>{{ money(report.aging?.total_outstanding) }}</strong>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="12">
        <h3 class="section-title">四路径占比</h3>
        <el-table :data="paths" size="small" stripe>
          <el-table-column prop="label" label="路径" />
          <el-table-column prop="count" label="订单数" width="90" align="right" />
          <el-table-column label="金额" width="120" align="right">
            <template #default="{ row }">{{ money(row.amount) }}</template>
          </el-table-column>
          <el-table-column prop="share_pct" label="占比%" width="90" align="right" />
        </el-table>
      </el-col>
      <el-col :span="12">
        <h3 class="section-title">应收账龄</h3>
        <el-table :data="agingBuckets" size="small" stripe>
          <el-table-column prop="label" label="账龄桶" />
          <el-table-column label="金额" align="right">
            <template #default="{ row }">{{ money(row.value) }}</template>
          </el-table-column>
        </el-table>
        <p class="hint">已确认回款 {{ money(report?.paid_amount) }} / 订单金额 {{ money(report?.order_amount) }}</p>
      </el-col>
    </el-row>

    <h3 class="section-title">负责人业绩</h3>
    <el-table :data="owners" size="small" stripe>
      <el-table-column prop="owner_name" label="负责人" min-width="120" />
      <el-table-column prop="won_deal_count" label="赢单" width="80" align="right" />
      <el-table-column prop="order_count" label="订单数" width="90" align="right" />
      <el-table-column label="成交金额" width="120" align="right">
        <template #default="{ row }">{{ money(row.order_amount) }}</template>
      </el-table-column>
      <el-table-column label="已回款" width="120" align="right">
        <template #default="{ row }">{{ money(row.paid_amount) }}</template>
      </el-table-column>
      <el-table-column prop="payment_rate" label="回款率%" width="100" align="right" />
    </el-table>
  </div>
</template>

<style scoped>
.trade-report__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.trade-report__title {
  margin: 0;
  font-size: 20px;
}
.trade-report__desc {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.trade-report__summary {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.metric {
  background: var(--el-fill-color-light);
  border-radius: 8px;
  padding: 12px;
}
.metric__label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
.metric strong {
  font-size: 20px;
}
.section-title {
  margin: 16px 0 8px;
  font-size: 15px;
}
.hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
@media (max-width: 960px) {
  .trade-report__summary {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
