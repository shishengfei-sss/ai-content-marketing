<script setup>
import { onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { analyticsApi } from '../api/client'

const lineRef = ref(null)
const pieRef = ref(null)
const stats = ref([
  { label: '总阅读量', value: '0' },
  { label: '总生成数', value: '0' },
  { label: '发布成功率', value: '—' },
  { label: '本月生成', value: '0' },
])

const platformMap = { wechat: '公众号', xhs: '小红书', douyin: '抖音' }

onMounted(async () => {
  try {
    const { data } = await analyticsApi.stats()
    stats.value = [
      { label: '总阅读量', value: data.total_reads.toLocaleString('zh-CN') },
      { label: '总生成数', value: String(data.total_generated) },
      { label: '发布成功率', value: `${data.publish_success_rate}%` },
      {
        label: '本月生成',
        value: String(data.monthly_generation.at(-1)?.count || 0),
      },
    ]

    if (lineRef.value) {
      echarts.init(lineRef.value).setOption({
        title: { text: '内容生成趋势', left: 0, textStyle: { fontSize: 14 } },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: data.monthly_generation.map((m) => m.month) },
        yAxis: { type: 'value' },
        series: [{
          type: 'bar',
          data: data.monthly_generation.map((m) => m.count),
          itemStyle: { color: '#1677ff' },
        }],
      })
    }
    if (pieRef.value) {
      echarts.init(pieRef.value).setOption({
        title: { text: '平台分布', left: 0, textStyle: { fontSize: 14 } },
        tooltip: { trigger: 'item' },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          data: Object.entries(data.platform_breakdown).map(([k, v]) => ({
            name: platformMap[k] || k,
            value: v,
          })),
        }],
      })
    }
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  }
})
</script>

<template>
  <div class="analytics-page">
    <el-row :gutter="16">
      <el-col v-for="item in stats" :key="item.label" :span="6">
        <div class="stat-card">
          <div class="stat-card__label">{{ item.label }}</div>
          <div class="stat-card__value">{{ item.value }}</div>
        </div>
      </el-col>
    </el-row>
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="14">
        <div class="page-card"><div ref="lineRef" style="height: 320px" /></div>
      </el-col>
      <el-col :span="10">
        <div class="page-card"><div ref="pieRef" style="height: 320px" /></div>
      </el-col>
    </el-row>
  </div>
</template>
