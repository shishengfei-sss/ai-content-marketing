<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { crmApi, formatApiError, isBenignEmptyError } from '../../api/client'
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
const stageDuration = ref(null)
/** 避免 onMounted / watch 并发加载时旧请求覆盖新结果或连弹错误 */
let loadSeq = 0
const EMPTY_FORECAST = { deal_count: 0, total_amount: 0, weighted_amount: 0, by_stage: [], by_owner: [] }
const EMPTY_WIN_LOSS = { total: 0, by_type: { won: 0, lost: 0, abandoned: 0 }, by_reason: [], items: [] }
const EMPTY_DURATION = { pipeline_id: null, pipeline_name: '', stages: [] }

const hasForecastData = computed(() => Number(forecast.value?.deal_count || 0) > 0)
const hasWinLossData = computed(() => Number(winLoss.value?.total || 0) > 0)
const durationStages = computed(() => stageDuration.value?.stages || [])

const funnelChartRef = ref(null)
let chartInstance = null

const FALLBACK_COLORS = ['#1677ff', '#69b1ff', '#95de64', '#ffc53d', '#ff7875', '#b37feb']

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

async function loadForecast(seq) {
  loading.value = true
  try {
    const params = {}
    if (pipelineId.value) params.pipeline_id = pipelineId.value
    if (ownerId.value) params.owner_id = ownerId.value
    const { data } = await crmApi.dealForecast(params)
    if (seq !== loadSeq) return
    forecast.value = data || { ...EMPTY_FORECAST }
  } catch (e) {
    if (seq !== loadSeq) return
    if (isBenignEmptyError(e)) {
      forecast.value = { ...EMPTY_FORECAST }
    } else {
      ElMessage.error(formatApiError(e, '加载预测失败'))
      forecast.value = { ...EMPTY_FORECAST }
    }
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

async function loadWinLoss(seq) {
  loading.value = true
  try {
    const { data } = await crmApi.dealWinLoss({})
    if (seq !== loadSeq) return
    winLoss.value = data || { ...EMPTY_WIN_LOSS }
  } catch (e) {
    if (seq !== loadSeq) return
    if (isBenignEmptyError(e)) {
      winLoss.value = { ...EMPTY_WIN_LOSS }
    } else {
      ElMessage.error(formatApiError(e, '加载赢输分析失败'))
      winLoss.value = { ...EMPTY_WIN_LOSS }
    }
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

async function loadStageDuration(seq) {
  loading.value = true
  try {
    const params = {}
    if (pipelineId.value) params.pipeline_id = pipelineId.value
    if (ownerId.value) params.owner_id = ownerId.value
    const { data } = await crmApi.dealStageDuration(params)
    if (seq !== loadSeq) return
    stageDuration.value = data || { ...EMPTY_DURATION }
  } catch (e) {
    if (seq !== loadSeq) return
    if (isBenignEmptyError(e)) {
      stageDuration.value = { ...EMPTY_DURATION }
    } else {
      ElMessage.error(formatApiError(e, '加载阶段停留失败'))
      stageDuration.value = { ...EMPTY_DURATION }
    }
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

async function loadActiveTab() {
  const seq = ++loadSeq
  if (activeTab.value === 'funnel') await loadFunnel(seq)
  else if (activeTab.value === 'forecast') await loadForecast(seq)
  else if (activeTab.value === 'duration') await loadStageDuration(seq)
  else await loadWinLoss(seq)
}

async function loadFunnel(seq) {
  if (!pipelineId.value) { stages.value = []; renderChart(); return }
  loading.value = true
  try {
    const params = { pipeline_id: pipelineId.value }
    if (ownerId.value) params.owner_id = ownerId.value
    const { data } = await crmApi.dealFunnel(params)
    if (seq !== loadSeq) return
    stages.value = Array.isArray(data) ? data : []
    renderChart()
  } catch (e) {
    if (seq !== loadSeq) return
    ElMessage.error(formatApiError(e, '加载漏斗失败'))
    stages.value = []
    renderChart()
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

function stageColor(stage, index) {
  return stage?.color || FALLBACK_COLORS[index % FALLBACK_COLORS.length]
}

/** 空阶段用递减占位，避免漏斗变成「宽顶 + 等宽细条」 */
function funnelVisualValue(stage, index, list) {
  const count = Number(stage.deal_count || 0)
  if (count > 0) return count
  const maxC = Math.max(...list.map((s) => Number(s.deal_count || 0)), 1)
  const n = list.length || 1
  return Math.max(0.12, maxC * (0.62 - (index / n) * 0.48))
}

function renderChart() {
  nextTick(() => {
    if (!funnelChartRef.value) return
    if (chartInstance && chartInstance.getDom() !== funnelChartRef.value) {
      chartInstance.dispose()
      chartInstance = null
    }
    if (!chartInstance) chartInstance = echarts.init(funnelChartRef.value)
    const list = stages.value
    if (!list.length) {
      chartInstance.clear()
      return
    }
    const data = list.map((s, i) => ({
      name: s.stage_name,
      value: funnelVisualValue(s, i, list),
      itemStyle: {
        color: stageColor(s, i),
        borderColor: '#fff',
        borderWidth: 1,
      },
    }))
    chartInstance.setOption({
      tooltip: {
        trigger: 'item',
        formatter: (p) => {
          const s = list[p.dataIndex]
          if (!s) return p.name
          return `${s.stage_name}<br/>商机：${s.deal_count}<br/>金额：¥${formatAmount(s.amount)}<br/>累计转化：${s.conversion_rate}%`
        },
      },
      series: [{
        type: 'funnel',
        left: '8%',
        width: '54%',
        top: 12,
        bottom: 12,
        minSize: '16%',
        maxSize: '100%',
        sort: 'none',
        gap: 4,
        label: {
          show: true,
          position: 'right',
          color: 'var(--el-text-color-primary, #1f1f1f)',
          fontSize: 12,
          formatter: (p) => {
            const s = list[p.dataIndex]
            if (!s) return p.name
            return `{name|${s.stage_name}}  {cnt|${s.deal_count}}`
          },
          rich: {
            name: { fontWeight: 500, color: '#1f1f1f' },
            cnt: { color: '#666', padding: [0, 0, 0, 2] },
          },
        },
        labelLine: {
          show: true,
          length: 12,
          lineStyle: { color: '#d9d9d9' },
        },
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 1,
        },
        data,
      }],
    }, true)
    chartInstance.resize()
  })
}

const totalAmount = computed(() => stages.value.reduce((s, x) => s + Number(x.amount || 0), 0))
const totalCount = computed(() => stages.value.reduce((s, x) => s + Number(x.deal_count || 0), 0))
const avgDealAmount = computed(() => {
  if (!totalCount.value) return 0
  return totalAmount.value / totalCount.value
})

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
  loadSeq += 1
})
function onResize() { chartInstance?.resize() }
watch(
  () => [pipelineId.value, ownerId.value, activeTab.value],
  () => loadActiveTab(),
)
watch(stages, () => renderChart(), { deep: true })
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
        <el-select v-model="ownerId" clearable placeholder="负责人" style="width: 140px">
          <el-option v-for="m in teamMembers" :key="m.user_id" :label="m.display_name || m.user_id" :value="m.user_id" />
        </el-select>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="deal-funnel__tabs">
      <el-tab-pane label="销售漏斗" name="funnel" />
      <el-tab-pane label="收入预测" name="forecast" />
      <el-tab-pane label="赢输分析" name="winloss" />
      <el-tab-pane label="阶段停留" name="duration" />
    </el-tabs>

    <template v-if="activeTab === 'funnel'">
      <div class="deal-funnel__summary">
        <div class="deal-funnel__metric">
          <span class="deal-funnel__metric-label">商机总数</span>
          <strong>{{ totalCount }}</strong>
        </div>
        <div class="deal-funnel__metric">
          <span class="deal-funnel__metric-label">金额合计</span>
          <strong>¥{{ formatAmount(totalAmount) }}</strong>
        </div>
        <div class="deal-funnel__metric">
          <span class="deal-funnel__metric-label">平均客单</span>
          <strong>¥{{ formatAmount(avgDealAmount) }}</strong>
        </div>
      </div>

      <el-empty v-if="!loading && totalCount === 0" description="暂无漏斗数据" class="deal-funnel__empty" />

      <div v-else-if="totalCount > 0" class="deal-funnel__body">
        <div class="deal-funnel__chart-wrap">
          <div ref="funnelChartRef" class="deal-funnel__chart" />
        </div>
        <el-table
          :data="stages"
          stripe
          size="small"
          class="deal-funnel__table"
          :header-cell-style="{ background: 'var(--el-fill-color-light)', color: 'var(--el-text-color-primary)', fontWeight: 600 }"
        >
          <el-table-column prop="stage_name" label="阶段" width="108">
            <template #default="{ row, $index }">
              <span class="deal-funnel__stage">
                <i class="deal-funnel__dot" :style="{ background: stageColor(row, $index) }" />
                <span class="deal-funnel__stage-name" :title="row.stage_name">{{ row.stage_name }}</span>
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="probability" label="概率" width="64" align="right">
            <template #default="{ row }">{{ row.probability }}%</template>
          </el-table-column>
          <el-table-column prop="deal_count" label="商机" width="56" align="right" />
          <el-table-column label="金额" min-width="108" align="right">
            <template #default="{ row }">¥{{ formatAmount(row.amount) }}</template>
          </el-table-column>
          <el-table-column label="累计转化" width="80" align="right">
            <template #default="{ row }">{{ row.conversion_rate }}%</template>
          </el-table-column>
          <el-table-column label="阶段转化" width="80" align="right">
            <template #default="{ row }">{{ row.stage_conversion_rate }}%</template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <template v-else-if="activeTab === 'forecast'">
      <template v-if="hasForecastData">
        <div class="deal-funnel__summary">
          <div class="deal-funnel__metric">
            <span class="deal-funnel__metric-label">进行中商机</span>
            <strong>{{ forecast.deal_count }}</strong>
          </div>
          <div class="deal-funnel__metric">
            <span class="deal-funnel__metric-label">金额合计</span>
            <strong>¥{{ formatAmount(forecast.total_amount) }}</strong>
          </div>
          <div class="deal-funnel__metric">
            <span class="deal-funnel__metric-label">加权预测</span>
            <strong>¥{{ formatAmount(forecast.weighted_amount) }}</strong>
          </div>
        </div>
        <el-table
          :data="forecast.by_stage || []"
          stripe
          size="small"
          class="deal-funnel__table deal-funnel__table--full"
          :header-cell-style="{ background: 'var(--el-fill-color-light)', color: 'var(--el-text-color-primary)', fontWeight: 600 }"
        >
          <el-table-column label="阶段" width="140">
            <template #default="{ row }">{{ stageName(row.stage_id) }}</template>
          </el-table-column>
          <el-table-column prop="deal_count" label="商机数" width="90" align="right" />
          <el-table-column label="金额" min-width="140" align="right">
            <template #default="{ row }">¥{{ formatAmount(row.amount) }}</template>
          </el-table-column>
          <el-table-column label="加权金额" min-width="140" align="right">
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
            <strong class="is-success">{{ winLoss.by_type?.won || 0 }}</strong>
          </div>
          <div class="deal-funnel__metric">
            <span class="deal-funnel__metric-label">输单</span>
            <strong class="is-danger">{{ winLoss.by_type?.lost || 0 }}</strong>
          </div>
          <div class="deal-funnel__metric">
            <span class="deal-funnel__metric-label">放弃</span>
            <strong>{{ winLoss.by_type?.abandoned || 0 }}</strong>
          </div>
        </div>
        <el-table
          :data="winLoss.by_reason || []"
          stripe
          size="small"
          class="deal-funnel__table deal-funnel__table--full"
          :header-cell-style="{ background: 'var(--el-fill-color-light)', color: 'var(--el-text-color-primary)', fontWeight: 600 }"
        >
          <el-table-column prop="reason" label="原因" min-width="200" />
          <el-table-column prop="count" label="次数" width="100" align="right" />
        </el-table>
      </template>
      <el-empty v-else-if="!loading" description="暂无赢输分析数据" class="deal-funnel__empty" />
    </template>

    <template v-else-if="activeTab === 'duration'">
      <p v-if="stageDuration?.pipeline_name" class="deal-funnel__pipeline-hint">
        管道：{{ stageDuration.pipeline_name }} · 基于阶段变更日志统计停留天数
      </p>
      <el-table
        v-if="durationStages.length"
        :data="durationStages"
        stripe
        size="small"
        class="deal-funnel__table deal-funnel__table--full"
        :header-cell-style="{ background: 'var(--el-fill-color-light)', color: 'var(--el-text-color-primary)', fontWeight: 600 }"
      >
        <el-table-column prop="stage_name" label="阶段" width="120" />
        <el-table-column prop="sample_count" label="样本数" width="90" align="right" />
        <el-table-column label="平均停留(天)" min-width="110" align="right">
          <template #default="{ row }">{{ row.avg_days }}</template>
        </el-table-column>
        <el-table-column label="最长停留(天)" min-width="110" align="right">
          <template #default="{ row }">{{ row.max_days }}</template>
        </el-table-column>
        <el-table-column label="SLA(天)" width="90" align="right">
          <template #default="{ row }">{{ row.max_stay_days ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="超SLA数" width="90" align="right">
          <template #default="{ row }">
            <span :class="{ 'is-danger': row.over_sla_count > 0 }">{{ row.over_sla_count }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!loading" description="暂无阶段停留数据" class="deal-funnel__empty" />
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
.deal-funnel__title {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 600;
}
.deal-funnel__desc {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.deal-funnel__filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.deal-funnel__tabs {
  margin-top: 4px;
}
.deal-funnel__tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}

.deal-funnel__summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.deal-funnel__metric {
  background: var(--el-fill-color-light);
  border-radius: 8px;
  padding: 12px 14px;
}
.deal-funnel__metric-label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
.deal-funnel__metric strong {
  font-size: 20px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-primary);
}
.deal-funnel__metric .is-success { color: var(--el-color-success); }
.deal-funnel__metric .is-danger { color: var(--el-color-danger); }

.deal-funnel__body {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(420px, 1.2fr);
  gap: 16px;
  align-items: start;
}
.deal-funnel__chart-wrap {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
  min-height: 320px;
}
.deal-funnel__chart {
  width: 100%;
  height: 320px;
}
.deal-funnel__table {
  width: 100%;
}
.deal-funnel__table--full {
  margin-top: 0;
}
.deal-funnel__table :deep(.el-table__inner-wrapper::before) {
  display: none;
}
.deal-funnel__table :deep(.el-table__cell) {
  padding: 8px 10px;
}
.deal-funnel__stage {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
}
.deal-funnel__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.deal-funnel__stage-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.deal-funnel__pipeline-hint {
  margin: 0 0 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.deal-funnel__empty {
  padding: 48px 0;
}
.is-danger {
  color: var(--el-color-danger);
  font-weight: 600;
}

@media (max-width: 1100px) {
  .deal-funnel__body {
    grid-template-columns: 1fr;
  }
  .deal-funnel__chart {
    height: 280px;
  }
}
@media (max-width: 640px) {
  .deal-funnel__summary {
    grid-template-columns: 1fr;
  }
}
</style>
