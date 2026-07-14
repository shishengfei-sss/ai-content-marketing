<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { crmApi, isBenignEmptyError } from '../../api/client'
import { useTeamMembers } from '../../composables/useTeamMembers'

const loading = ref(false)
const pipelines = ref([])
const pipelineId = ref('')
const ownerId = ref('')
const { members: teamMembers, loadMembers } = useTeamMembers()
const stages = ref([])
const activeTab = ref('funnel')
const forecast = ref(null)
const winLoss = ref(null)
const EMPTY_FORECAST = { deal_count: 0, total_amount: 0, weighted_amount: 0, by_stage: [], by_owner: [] }
const EMPTY_WIN_LOSS = { total: 0, by_type: { won: 0, lost: 0, abandoned: 0 }, by_reason: [], items: [] }

const hasForecastData = computed(() => Number(forecast.value?.deal_count || 0) > 0)
const hasWinLossData = computed(() => Number(winLoss.value?.total || 0) > 0)

const funnelChartRef = ref(null)
let chartInstance = null

async function loadPipelines() {
  try {
    const { data } = await crmApi.listPipelines()
    pipelines.value = Array.isArray(data) ? data : []
    const def = pipelines.value.find((p) => p.is_default) || pipelines.value[0]
    pipelineId.value = def?.id || ''
  } catch { pipelines.value = [] }
}

async function loadTeamMembers() {
  await loadMembers()
}

async function loadForecast() {
  loading.value = true
  try {
    const params = {}
    if (pipelineId.value) params.pipeline_id = pipelineId.value
    if (ownerId.value) params.owner_id = ownerId.value
    const { data } = await crmApi.dealForecast(params)
    forecast.value = data || { ...EMPTY_FORECAST }
  } catch (e) {
    if (isBenignEmptyError(e)) {
      forecast.value = { ...EMPTY_FORECAST }
    } else {
      ElMessage.error(e.message || '加载预测失败')
      forecast.value = { ...EMPTY_FORECAST }
    }
  } finally {
    loading.value = false
  }
}

async function loadWinLoss() {
  loading.value = true
  try {
    const { data } = await crmApi.dealWinLoss({})
    winLoss.value = data || { ...EMPTY_WIN_LOSS }
  } catch (e) {
    if (isBenignEmptyError(e)) {
      winLoss.value = { ...EMPTY_WIN_LOSS }
    } else {
      ElMessage.error(e.message || '加载赢输分析失败')
      winLoss.value = { ...EMPTY_WIN_LOSS }
    }
  } finally {
    loading.value = false
  }
}

async function loadActiveTab() {
  if (activeTab.value === 'funnel') await loadFunnel()
  else if (activeTab.value === 'forecast') await loadForecast()
  else await loadWinLoss()
}

async function loadFunnel() {
  if (!pipelineId.value) { stages.value = []; renderChart(); return }
  loading.value = true
  try {
    const params = { pipeline_id: pipelineId.value }
    if (ownerId.value) params.owner_id = ownerId.value
    const { data } = await crmApi.dealFunnel(params)
    stages.value = Array.isArray(data) ? data : []
    renderChart()
  } catch (e) {
    ElMessage.error(e.message || '加载漏斗失败')
    stages.value = []
    renderChart()
  } finally {
    loading.value = false
  }
}

function renderChart() {
  nextTick(() => {
    if (!funnelChartRef.value) return
    if (!chartInstance) chartInstance = echarts.init(funnelChartRef.value)
    const data = stages.value.map((s) => ({
      name: `${s.stage_name} (${s.deal_count})`,
      value: s.deal_count,
      amount: s.amount,
      color: s.color,
    }))
    chartInstance.setOption({
      tooltip: {
        trigger: 'item',
        formatter: (p) => {
          const s = stages.value[p.dataIndex]
          if (!s) return p.name
          return `${s.stage_name}<br/>商机数：${s.deal_count}<br/>金额：¥${s.amount}<br/>累计转化：${s.conversion_rate}%`
        },
      },
      series: [{
        type: 'funnel',
        left: '10%',
        right: '10%',
        top: 16,
        bottom: 16,
        minSize: '12%',
        label: { show: true, position: 'inside', formatter: '{b}' },
        data,
      }],
      color: stages.value.map((s) => s.color || '#409EFF'),
    })
  })
}

const totalAmount = computed(() => stages.value.reduce((s, x) => s + Number(x.amount || 0), 0))
const totalCount = computed(() => stages.value.reduce((s, x) => s + Number(x.deal_count || 0), 0))

function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function stageName(stageId) {
  for (const p of pipelines.value) {
    const s = (p.stages || []).find((x) => String(x.id) === String(stageId))
    if (s) return s.name
  }
  return stageId
}

onMounted(async () => {
  await Promise.all([loadPipelines(), loadTeamMembers()])
  await loadActiveTab()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chartInstance?.dispose()
})
function onResize() { chartInstance?.resize() }
watch(() => [pipelineId.value, ownerId.value, activeTab.value], () => loadActiveTab())
</script>

<template>
  <div v-loading="loading" class="page-card deal-funnel">
    <div class="deal-funnel__header">
      <div>
        <h2 class="deal-funnel__title">销售漏斗</h2>
        <p class="deal-funnel__desc">按商机阶段聚合数量与金额，洞察阶段转化率</p>
      </div>
      <div class="deal-funnel__filters">
        <el-select v-model="pipelineId" placeholder="销售管道" style="width: 180px">
          <el-option v-for="p in pipelines" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="ownerId" clearable placeholder="负责人" style="width: 160px">
          <el-option v-for="m in teamMembers" :key="m.user_id" :label="m.display_name || m.user_id" :value="m.user_id" />
        </el-select>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="deal-funnel__tabs">
      <el-tab-pane label="销售漏斗" name="funnel" />
      <el-tab-pane label="收入预测" name="forecast" />
      <el-tab-pane label="赢输分析" name="winloss" />
    </el-tabs>

    <template v-if="activeTab === 'funnel'">
    <div class="deal-funnel__summary">
      <div class="deal-funnel__metric">
        <span class="deal-funnel__metric-label">商机总数</span>
        <span class="deal-funnel__metric-value">{{ totalCount }}</span>
      </div>
      <div class="deal-funnel__metric">
        <span class="deal-funnel__metric-label">金额合计</span>
        <span class="deal-funnel__metric-value">¥{{ formatAmount(totalAmount) }}</span>
      </div>
    </div>

    <div ref="funnelChartRef" class="deal-funnel__chart" />

    <el-empty v-if="!loading && totalCount === 0" description="暂无漏斗数据" class="deal-funnel__empty" />

    <el-table v-else :data="stages" border size="small" class="deal-funnel__table">
      <el-table-column prop="stage_name" label="阶段" min-width="140" />
      <el-table-column prop="probability" label="成交概率" width="100" align="right">
        <template #default="{ row }">{{ row.probability }}%</template>
      </el-table-column>
      <el-table-column prop="deal_count" label="商机数" width="100" align="right" />
      <el-table-column label="金额" width="140" align="right">
        <template #default="{ row }">¥{{ formatAmount(row.amount) }}</template>
      </el-table-column>
      <el-table-column label="累计转化率" width="120" align="right">
        <template #default="{ row }">{{ row.conversion_rate }}%</template>
      </el-table-column>
      <el-table-column label="阶段间转化" width="120" align="right">
        <template #default="{ row }">{{ row.stage_conversion_rate }}%</template>
      </el-table-column>
    </el-table>
    </template>

    <template v-else-if="activeTab === 'forecast'">
      <template v-if="hasForecastData">
      <div class="deal-funnel__summary">
        <div class="deal-funnel__metric">
          <span class="deal-funnel__metric-label">进行中商机</span>
          <span class="deal-funnel__metric-value">{{ forecast.deal_count }}</span>
        </div>
        <div class="deal-funnel__metric">
          <span class="deal-funnel__metric-label">金额合计</span>
          <span class="deal-funnel__metric-value">¥{{ formatAmount(forecast.total_amount) }}</span>
        </div>
        <div class="deal-funnel__metric">
          <span class="deal-funnel__metric-label">加权预测</span>
          <span class="deal-funnel__metric-value">¥{{ formatAmount(forecast.weighted_amount) }}</span>
        </div>
      </div>
      <el-table :data="forecast.by_stage || []" border size="small" class="deal-funnel__table">
        <el-table-column label="阶段" min-width="160">
          <template #default="{ row }">{{ stageName(row.stage_id) }}</template>
        </el-table-column>
        <el-table-column prop="deal_count" label="商机数" width="100" align="right" />
        <el-table-column label="金额" width="140" align="right">
          <template #default="{ row }">¥{{ formatAmount(row.amount) }}</template>
        </el-table-column>
        <el-table-column label="加权金额" width="140" align="right">
          <template #default="{ row }">¥{{ formatAmount(row.weighted_amount) }}</template>
        </el-table-column>
      </el-table>
      </template>
      <el-empty v-else-if="!loading" description="暂无收入预测数据" class="deal-funnel__empty" />
    </template>

    <template v-else-if="activeTab === 'winloss'">
      <template v-if="hasWinLossData">
      <div class="deal-funnel__summary">
        <div class="deal-funnel__metric">
          <span class="deal-funnel__metric-label">赢单</span>
          <span class="deal-funnel__metric-value">{{ winLoss.by_type?.won || 0 }}</span>
        </div>
        <div class="deal-funnel__metric">
          <span class="deal-funnel__metric-label">输单</span>
          <span class="deal-funnel__metric-value">{{ winLoss.by_type?.lost || 0 }}</span>
        </div>
        <div class="deal-funnel__metric">
          <span class="deal-funnel__metric-label">放弃</span>
          <span class="deal-funnel__metric-value">{{ winLoss.by_type?.abandoned || 0 }}</span>
        </div>
      </div>
      <el-table :data="winLoss.by_reason || []" border size="small" class="deal-funnel__table">
        <el-table-column prop="reason" label="原因" min-width="200" />
        <el-table-column prop="count" label="次数" width="100" align="right" />
      </el-table>
      </template>
      <el-empty v-else-if="!loading" description="暂无赢输分析数据" class="deal-funnel__empty" />
    </template>
  </div>
</template>

<style scoped>
.deal-funnel__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}
.deal-funnel__title { margin: 0 0 4px; font-size: 18px; font-weight: 600; }
.deal-funnel__desc { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.deal-funnel__filters { display: flex; gap: 8px; }
.deal-funnel__summary { display: flex; gap: 24px; margin: 16px 0; }
.deal-funnel__metric { display: flex; flex-direction: column; gap: 2px; }
.deal-funnel__metric-label { font-size: 12px; color: var(--el-text-color-secondary); }
.deal-funnel__metric-value { font-size: 20px; font-weight: 600; color: var(--el-color-primary); }
.deal-funnel__chart { width: 100%; height: 320px; margin-bottom: 16px; }
.deal-funnel__table { margin-top: 8px; }
.deal-funnel__tabs { margin-bottom: 12px; }
.deal-funnel__empty { padding: 48px 0; }
</style>
