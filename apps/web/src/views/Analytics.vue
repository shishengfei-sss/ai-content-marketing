<script setup>
import { onMounted, ref } from 'vue'
import * as echarts from 'echarts'

const lineRef = ref(null)
const pieRef = ref(null)

onMounted(() => {
  if (lineRef.value) {
    echarts.init(lineRef.value).setOption({
      title: { text: '内容生成趋势', left: 0, textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'] },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: [12, 18, 25, 22, 30, 38], itemStyle: { color: '#1677ff' } }],
    })
  }
  if (pieRef.value) {
    echarts.init(pieRef.value).setOption({
      title: { text: '平台分布', left: 0, textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'item' },
      series: [
        {
          type: 'pie',
          radius: ['40%', '70%'],
          data: [
            { value: 45, name: '公众号' },
            { value: 30, name: '小红书' },
            { value: 25, name: '抖音' },
          ],
        },
      ],
    })
  }
})
</script>

<template>
  <div class="analytics-page">
    <el-row :gutter="16">
      <el-col :span="6" v-for="item in [
        { label: '总阅读量', value: '12,580' },
        { label: '总分享数', value: '386' },
        { label: '本月生成', value: '38 篇' },
        { label: '发布成功率', value: '96%' },
      ]" :key="item.label">
        <div class="stat-card">
          <div class="stat-card__label">{{ item.label }}</div>
          <div class="stat-card__value">{{ item.value }}</div>
        </div>
      </el-col>
    </el-row>
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="14">
        <div class="page-card">
          <div ref="lineRef" style="height: 320px" />
        </div>
      </el-col>
      <el-col :span="10">
        <div class="page-card">
          <div ref="pieRef" style="height: 320px" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>
