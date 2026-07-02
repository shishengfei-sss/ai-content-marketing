<script setup>
import { onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { useRouter } from 'vue-router'

const router = useRouter()
const chartRef = ref(null)

const stats = [
  { label: '待审核', value: 5, primary: true },
  { label: '今日排期', value: 2, primary: false },
  { label: '近7日阅读', value: '1,286', primary: false },
  { label: '本月生成', value: 38, primary: false },
]

const shortcuts = [
  { title: '新建公众号文章', desc: 'AI 生成财税营销内容', icon: 'ChatDotRound', path: '/create' },
  { title: '小红书导出', desc: '文案 + 封面一键打包', icon: 'Picture', path: '/contents' },
  { title: '上传知识库', desc: '导入公司服务资料', icon: 'Upload', path: '/knowledge' },
  { title: '配置 AI 模型', desc: 'DeepSeek / 其他大模型', icon: 'Cpu', path: '/settings/llm' },
]

const pendingList = [
  { title: '3月报税截止提醒', platform: '公众号', author: '李编辑', time: '10 分钟前' },
  { title: '小规模记账服务介绍', platform: '小红书', author: '王编辑', time: '1 小时前' },
  { title: '企业所得税汇算清缴', platform: '抖音', author: '张编辑', time: '2 小时前' },
]

onMounted(() => {
  if (!chartRef.value) return
  const chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      axisLine: { lineStyle: { color: '#e8e8e8' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    series: [
      {
        name: '阅读量',
        type: 'line',
        smooth: true,
        data: [120, 180, 150, 220, 190, 280, 256],
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
            <el-button type="primary" link size="small">审核</el-button>
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
