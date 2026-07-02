<script setup>
const events = [
  { date: '2026-03-28', title: '3月报税提醒', time: '09:00', status: 'scheduled' },
  { date: '2026-03-29', title: '代理记账优势', time: '10:30', status: 'scheduled' },
  { date: '2026-03-30', title: '发票管理技巧', time: '14:00', status: 'draft' },
]
</script>

<template>
  <div class="calendar-page">
    <el-row :gutter="16">
      <el-col :span="16">
        <div class="page-card">
          <div class="page-title">发布日历</div>
          <el-calendar />
        </div>
      </el-col>
      <el-col :span="8">
        <div class="page-card">
          <div class="page-title">近期排期</div>
          <div v-for="ev in events" :key="ev.title" class="schedule-item">
            <div class="schedule-item__date">{{ ev.date }}</div>
            <div class="schedule-item__body">
              <div class="schedule-item__title">{{ ev.title }}</div>
              <div class="schedule-item__meta">
                {{ ev.time }}
                <el-tag
                  :type="ev.status === 'scheduled' ? 'success' : 'info'"
                  size="small"
                >
                  {{ ev.status === 'scheduled' ? '已排期' : '草稿' }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.schedule-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border);
}

.schedule-item__date {
  font-size: 13px;
  color: var(--color-primary);
  font-weight: 600;
  width: 90px;
  flex-shrink: 0;
}

.schedule-item__title {
  font-weight: 500;
  margin-bottom: 4px;
}

.schedule-item__meta {
  font-size: 12px;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
