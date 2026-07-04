<script setup>
import { onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { contentApi, dashboardApi } from '../api/client'

const router = useRouter()
const apiBase = import.meta.env.VITE_API_BASE_URL || ''
const chartRef = ref(null)
const chartRange = ref('week')
let chartInstance = null
let readsBase = 200

const stats = ref([
  { label: '我的草稿', value: 0, primary: true },
  { label: '今日排期', value: 0, primary: false },
  { label: '近7日阅读', value: 0, primary: false },
  { label: '本月生成', value: 0, primary: false },
])

const shortcuts = [
  { title: '新建公众号文章', desc: 'AI 生成财税营销内容', icon: 'ChatDotRound', path: '/create' },
  { title: '小红书导出', desc: '文案 + 封面一键打包', icon: 'Picture', path: '/contents' },
  { title: '上传知识库', desc: '导入个人服务资料', icon: 'Upload', path: '/knowledge' },
  { title: '配置 AI 模型', desc: 'DeepSeek / 其他大模型', icon: 'Cpu', path: '/settings/llm' },
]

const contentList = ref([])
const contentPage = ref(1)
const contentTotal = ref(0)
const contentPageSize = 10
const contentLoading = ref(false)

const statusMap = {
  draft: { label: '草稿', type: 'info' },
  scheduled: { label: '已排期', type: '' },
  publishing: { label: '发布中', type: 'warning' },
  published: { label: '已发布', type: 'success' },
  failed: { label: '发布失败', type: 'danger' },
  exported: { label: '已导出', type: 'info' },
}

const platformMap = { wechat: '公众号', xhs: '小红书', douyin: '抖音' }

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

function openPreview(url) {
  if (!url) return
  window.open(url, '_blank')
}

async function loadContentBox() {
  contentLoading.value = true
  try {
    const { data } = await contentApi.list({
      page: contentPage.value,
      page_size: contentPageSize,
    })
    contentTotal.value = data.total
    contentList.value = data.items.map((item) => ({
      id: item.id,
      title: item.topic,
      platform: platformMap[item.platform] || item.platform,
      platformCode: item.platform,
      status: item.status,
      time: formatTime(item.updated_at || item.created_at),
      previewUrl: item.preview_url ? `${apiBase}${item.preview_url}` : '',
    }))
  } catch (e) {
    ElMessage.error(e.message || '加载内容箱失败')
  } finally {
    contentLoading.value = false
  }
}

function onContentPageChange() {
  loadContentBox()
}

function buildTrendSeries(range, base) {
  if (range === 'week') {
    return {
      labels: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      data: [0.7, 0.9, 0.8, 1.1, 0.95, 1.3, 1.0].map((n) => Math.round(base * n)),
    }
  }

  const labels = []
  const data = []
  const dailyAvg = base / 7
  const now = new Date()

  for (let i = 29; i >= 0; i--) {
    const date = new Date(now)
    date.setDate(date.getDate() - i)
    labels.push(`${date.getMonth() + 1}/${date.getDate()}`)
    const factor = 0.65 + 0.35 * Math.sin(i / 4) + (i % 7) * 0.04
    data.push(Math.max(0, Math.round(dailyAvg * factor)))
  }

  return { labels, data }
}

function renderChart() {
  if (!chartRef.value) return
  const { labels, data } = buildTrendSeries(chartRange.value, readsBase)
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: '#e8e8e8' } },
      axisLabel: { interval: chartRange.value === 'month' ? 4 : 0 },
    },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f0f0f0' } } },
    series: [
      {
        name: '阅读量',
        type: 'line',
        smooth: true,
        data,
        itemStyle: { color: '#1677ff' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(22,119,255,0.3)' },
              { offset: 1, color: 'rgba(22,119,255,0.02)' },
            ],
          },
        },
      },
    ],
  })
}

watch(chartRange, renderChart)

onMounted(async () => {
  try {
    const { data: dash } = await dashboardApi.stats()
    stats.value = [
      { label: '我的草稿', value: dash.draft_count, primary: true },
      { label: '今日排期', value: dash.today_scheduled, primary: false },
      {
        label: '近7日阅读',
        value: dash.reads_last_7_days.toLocaleString('zh-CN'),
        primary: false,
      },
      { label: '本月生成', value: dash.generated_this_month, primary: false },
    ]
    await loadContentBox()
  } catch (e) {
    ElMessage.error(e.message || '加载工作台数据失败')
  }

  const reads = stats.value[2].value
  readsBase =
    typeof reads === 'number' ? reads : parseInt(String(reads).replace(/,/g, ''), 10) || 200
  renderChart()
})
</script>

<template>
  <div class="dashboard">
    <el-row :gutter="16" class="dashboard__stats">
      <el-col v-for="stat in stats" :key="stat.label" :span="6">
        <div class="stat-card">
          <div class="stat-card__label">{{ stat.label }}</div>
          <div
            class="stat-card__value"
            :class="{ 'stat-card__value--primary': stat.primary }"
          >
            {{ stat.value }}
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="dashboard__row">
      <el-col :span="16">
        <div class="page-card">
          <div class="page-card__header">
            <span class="page-card__title">阅读趋势</span>
            <el-radio-group v-model="chartRange" size="small">
              <el-radio-button value="week">近7天</el-radio-button>
              <el-radio-button value="month">近30天</el-radio-button>
            </el-radio-group>
          </div>
          <div ref="chartRef" class="dashboard__chart" />
        </div>
      </el-col>
      <el-col :span="8">
        <div class="page-card dashboard__shortcuts">
          <div class="page-card__title">快捷入口</div>
          <div
            v-for="item in shortcuts"
            :key="item.title"
            class="shortcut-item"
            @click="router.push(item.path)"
          >
            <el-icon class="shortcut-item__icon" :size="24">
              <component :is="item.icon" />
            </el-icon>
            <div>
              <div class="shortcut-item__title">{{ item.title }}</div>
              <div class="shortcut-item__desc">{{ item.desc }}</div>
            </div>
            <el-icon class="shortcut-item__arrow"><ArrowRight /></el-icon>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="page-card dashboard__pending">
      <div class="page-card__header">
        <span class="page-card__title">内容箱</span>
        <el-button type="primary" link @click="router.push('/contents')">
          查看全部
        </el-button>
      </div>
      <el-table
        v-loading="contentLoading"
        :data="contentList"
        stripe
        empty-text="暂无内容，去创作页生成吧"
      >
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="platform" label="平台" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.platform }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type || 'info'" size="small">
              {{ statusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="time" label="更新时间" width="160" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button
              v-if="row.previewUrl"
              type="primary"
              link
              size="small"
              @click="openPreview(row.previewUrl)"
            >
              预览
            </el-button>
            <el-button
              v-if="row.status === 'draft'"
              type="primary"
              link
              size="small"
              @click="router.push('/create')"
            >
              继续编辑
            </el-button>
            <el-button
              v-if="row.platformCode === 'wechat' && (row.status === 'draft' || row.status === 'failed')"
              type="primary"
              link
              size="small"
              @click="router.push('/contents')"
            >
              去发布
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="dashboard__pagination">
        <el-pagination
          v-model:current-page="contentPage"
          background
          layout="total, prev, pager, next"
          :total="contentTotal"
          :page-size="contentPageSize"
          @current-change="onContentPageChange"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard__stats {
  margin-bottom: 16px;
}

.dashboard__row {
  margin-bottom: 16px;
}

.page-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-card__title {
  font-size: 16px;
  font-weight: 600;
}

.dashboard__chart {
  height: 280px;
}

.dashboard__pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.shortcut-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.shortcut-item:hover {
  background: #f5f5f5;
}

.shortcut-item + .shortcut-item {
  border-top: 1px solid var(--color-border);
}

.shortcut-item__icon {
  color: var(--color-primary);
  flex-shrink: 0;
}

.shortcut-item__title {
  font-weight: 500;
  margin-bottom: 2px;
}

.shortcut-item__desc {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.shortcut-item__arrow {
  margin-left: auto;
  color: var(--color-text-muted);
}
</style>
