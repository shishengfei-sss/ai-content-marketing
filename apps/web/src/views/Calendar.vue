<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { contentApi } from '../api/client'

const loading = ref(true)
const events = ref([])

const platformMap = {
  wechat: '公众号',
  xhs: '小红书',
  douyin: '抖音',
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('zh-CN')
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

onMounted(async () => {
  try {
    const { data } = await contentApi.calendar()
    events.value = data.map((item) => ({
      id: item.id,
      date: formatDate(item.scheduled_at),
      title: item.title,
      time: formatTime(item.scheduled_at),
      status: item.status,
      platform: platformMap[item.platform] || item.platform,
    }))
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="calendar-page">
    <div class="page-card">
      <el-empty v-if="!loading && !events.length" description="暂无排期内容" />
      <div v-else v-loading="loading">
        <div v-for="ev in events" :key="ev.id" class="schedule-item">
          <div class="schedule-item__date">{{ ev.date }}</div>
          <div class="schedule-item__body">
            <div class="schedule-item__title">{{ ev.title }}</div>
            <div class="schedule-item__meta">
              <span>{{ ev.time }} · {{ ev.platform }}</span>
              <el-tag
                size="small"
                :type="ev.status === 'published' ? 'success' : ev.status === 'scheduled' ? 'warning' : 'info'"
              >
                {{ ev.status === 'scheduled' ? '已排期' : ev.status === 'published' ? '已发布' : ev.status }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.schedule-item {
  display: flex;
  gap: 16px;
  padding: 16px 0;
  border-bottom: 1px solid var(--color-border);
}

.schedule-item__date {
  width: 100px;
  font-weight: 600;
  color: var(--color-primary);
  flex-shrink: 0;
}

.schedule-item__title {
  font-size: 15px;
  margin-bottom: 6px;
}

.schedule-item__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: var(--color-text-secondary);
}
</style>
