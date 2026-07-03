<script setup>
import { onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { contentApi, dashboardApi } from '../api/client'

const router = useRouter()
const chartRef = ref(null)

const stats = ref([
  { label: '待审核', value: 0, primary: true },
  { label: '今日排期', value: 0, primary: false },
  { label: '近7日阅读', value: 0, primary: false },
  { label: '本月生成', value: 0, primary: false },
])

const shortcuts = [
  { title: '新建公众号文章', desc: 'AI 生成财税营销内容', icon: 'ChatDotRound', path: '/create' },
  { title: '小红书导出', desc: '文案 + 封面一键打包', icon: 'Picture', path: '/contents' },
  { title: '上传知识库', desc: '导入公司服务资料', icon: 'Upload', path: '/knowledge' },
  { title: '配置 AI 模型', desc: 'DeepSeek / 其他大模型', icon: 'Cpu', path: '/settings/llm' },
]

const pendingList = ref([])

const platformMap = { wechat: '公众号', xhs: '小红书', douyin: '抖音' }

function formatRelative(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  return new Date(iso).toLocaleDateString('zh-CN')
}

onMounted(async () => {
  try {
    const [{ data: dash }, { data: pending }] = await Promise.all([
      dashboardApi.stats(),
      contentApi.list({ status: 'pending_review', page_size: 5 }),
    ])
    stats.value = [
      { label: '待审核', value: dash.pending_review, primary: true },
      { label: '今日排期', value: dash.today_scheduled, primary: false },
      {
        label: '近7日阅读',
        value: dash.reads_last_7_days.toLocaleString('zh-CN'),
        primary: false,
      },
      { label: '本月生成', value: dash.generated_this_month, primary: false },
    ]
    pendingList.value = pending.items.map((item) => ({
      id: item.id,
      title: item.topic,
      platform: platformMap[item.platform] || item.platform,
      author: item.author_name || '—',
      time: formatRelative(item.updated_at || item.created_at),
    }))
  } catch (e) {
    ElMessage.error(e.message || '加载工作台数据失败')
  }

  if (!chartRef.value) return
  const reads = stats.value[2].value
  const base = typeof reads === 'number' ? reads : parseInt(String(reads).replace(/,/g, ''), 10) || 200
  const chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      axisLine: { lineStyle: { color: '#e8e8e8' } },
    },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f0f0f0' } } },
    series: [
      {
        name: '阅读量',
        type: 'line',
        smooth: true,
        data: [0.7, 0.9, 0.8, 1.1, 0.95, 1.3, 1.0].map((n) => Math.round(base * n)),
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
            <el-radio-group size="small" model-value="week">
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
        <span class="page-card__title">待审核内容</span>
        <el-button type="primary" link @click="router.push('/contents')">
          查看全部
        </el-button>
      </div>
      <el-table :data="pendingList" stripe>
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="platform" label="平台" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.platform }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="author" label="提交人" width="100" />
        <el-table-column prop="time" label="时间" width="120" />
        <el-table-column label="操作" width="120">
          <template #default>
            <el-button type="primary" link size="small" @click="router.push('/contents')">
              审核
            </el-button>
          </template>
        </el-table-column>
      </el-table>
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
