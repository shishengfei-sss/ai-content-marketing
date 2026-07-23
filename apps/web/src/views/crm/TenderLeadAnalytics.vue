<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { crmApi } from '../../api/client'

const loading = ref(false)
const data = ref(null)

async function load() {
  loading.value = true
  try {
    const { data: res } = await crmApi.getTenderLeadAnalytics()
    data.value = res
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="analytics-page" v-loading="loading">
    <div class="page-card analytics-page__head">
      <h2>招标线索效果看板</h2>
      <p class="hint">跟进与转化（不含平台入库量）</p>
    </div>

    <div v-if="data" class="stat-row">
      <div class="stat-card">
        <div class="stat-card__label">跟进率</div>
        <div class="stat-card__value">{{ data.follow_rate }}%</div>
        <div class="stat-card__sub">已处理 / 推送 {{ data.total_pushed }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">线索→商机转化率</div>
        <div class="stat-card__value">{{ data.conversion_rate }}%</div>
        <div class="stat-card__sub">转商机 {{ data.converted_to_deal_count }} / 推送 {{ data.total_pushed }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">高匹配占比</div>
        <div class="stat-card__value">{{ data.high_match_rate }}%</div>
        <div class="stat-card__sub">≥60 分 {{ data.high_match_count }} 条</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">无效/过期占比</div>
        <div class="stat-card__value">{{ data.invalid_expired_rate }}%</div>
        <div class="stat-card__sub">{{ data.invalid_expired_count }} 条</div>
      </div>
    </div>

    <div v-if="data" class="page-card" style="margin-top: 16px">
      <h3 class="section-title">匹配度分布</h3>
      <el-table :data="data.score_buckets || []" border size="small">
        <el-table-column prop="bucket" label="匹配度区间" />
        <el-table-column prop="count" label="线索数" width="120" />
        <el-table-column label="占比">
          <template #default="{ row }">
            <el-progress
              :percentage="data.total_pushed ? Math.round(100 * row.count / data.total_pushed) : 0"
              :stroke-width="12"
            />
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div v-if="data" class="page-card" style="margin-top: 16px">
      <h3 class="section-title">近 8 周趋势</h3>
      <el-table :data="data.weekly_trend || []" border size="small">
        <el-table-column prop="week" label="周起始" min-width="120" />
        <el-table-column prop="pushed" label="推送量" width="100" />
        <el-table-column prop="claimed" label="纳入线索" width="100" />
        <el-table-column prop="converted" label="转商机" width="100" />
        <el-table-column prop="conversion_rate" label="转化率%" width="100" />
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.analytics-page__head h2 { margin: 0 0 4px; font-size: 18px; }
.hint { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 12px;
}
@media (max-width: 960px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
}
.stat-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 16px;
}
.stat-card__label { font-size: 13px; color: var(--el-text-color-secondary); }
.stat-card__value { font-size: 28px; font-weight: 600; margin: 6px 0; }
.stat-card__sub { font-size: 12px; color: var(--el-text-color-placeholder); }
.section-title { margin: 0 0 12px; font-size: 15px; }
</style>
