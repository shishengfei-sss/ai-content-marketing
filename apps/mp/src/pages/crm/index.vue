<template>
  <view class="page">
    <view class="banner">
      <text class="banner__title">销售管理</text>
      <text class="banner__sub">线索 · 客户 · 任务</text>
    </view>

    <view v-if="!menuItems.length" class="empty-page">
      <text class="empty-page__title">暂无销售模块权限</text>
      <text class="empty-page__sub">请联系管理员开通线索、客户或任务权限</text>
    </view>

    <template v-else>
      <view v-if="stats.length" class="cards">
        <view
          v-for="item in stats"
          :key="item.key"
          class="card"
          :class="{ 'card--warn': item.warn }"
          @click="go(item.url)"
        >
          <text class="card__label">{{ item.label }}</text>
          <text class="card__value">{{ item.value }}</text>
          <text class="card__hint">{{ item.hint }}</text>
        </view>
      </view>

      <view class="section">
        <view class="section__header">
          <text class="section__title">功能入口</text>
        </view>
        <view class="grid">
          <view v-for="item in menuItems" :key="item.url" class="grid-item" @click="go(item.url)">
            <text class="grid-item__title">{{ item.title }}</text>
            <text class="grid-item__desc">{{ item.desc }}</text>
          </view>
        </view>
      </view>

      <view v-if="openTasks.length" class="section">
        <view class="section__header">
          <text class="section__title">待办任务</text>
          <text class="section__link" @click="go('/pages/crm/tasks')">查看全部</text>
        </view>
        <view v-for="task in openTasks" :key="task.id" class="list-item" @click="go('/pages/crm/tasks')">
          <view class="list-item__main">
            <text class="list-item__title">{{ task.title }}</text>
            <text class="list-item__sub">{{ task.dueLabel }}</text>
          </view>
          <text class="list-item__badge">{{ task.statusLabel }}</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import { crmApi, dashboardApi } from '@/utils/api'
import { CRM_MENU, filterMenuByPermission, hasAnyPermission } from '@/utils/permissions'
import { ensureSession } from '@/utils/session'

const permissions = ref([])
const dash = ref({})
const openTasks = ref([])

const menuItems = computed(() => filterMenuByPermission(CRM_MENU, permissions.value))

const canListTasks = computed(() =>
  hasAnyPermission(permissions.value, [
    'crm.task.list_own',
    'crm.task.list_team',
    'crm.task.list_territory',
    'crm.task.list_all',
  ]),
)

const canListLeads = computed(() =>
  hasAnyPermission(permissions.value, [
    'crm.lead.list_own',
    'crm.lead.list_team',
    'crm.lead.list_territory',
    'crm.lead.list_all',
  ]),
)

const stats = computed(() => {
  const items = []
  if (canListLeads.value) {
    items.push({
      key: 'crm_new_leads',
      label: '近7日新线索',
      value: dash.value.crm_new_leads ?? 0,
      hint: '点击查看线索',
      url: '/pages/crm/leads',
    })
  }
  if (canListTasks.value) {
    items.push({
      key: 'crm_tasks_due_today',
      label: '今日待办',
      value: dash.value.crm_tasks_due_today ?? 0,
      hint: '点击查看任务',
      url: '/pages/crm/tasks',
    })
    items.push({
      key: 'crm_tasks_overdue',
      label: '逾期任务',
      value: dash.value.crm_tasks_overdue ?? 0,
      hint: '请尽快处理',
      url: '/pages/crm/tasks',
      warn: (dash.value.crm_tasks_overdue ?? 0) > 0,
    })
  }
  return items
})

const taskStatusMap = { open: '待办', in_progress: '进行中', on_hold: '已挂起', done: '已完成', cancelled: '已取消' }

function formatDue(iso) {
  if (!iso) return '无截止时间'
  return new Date(iso).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
}

async function loadData() {
  const user = await ensureSession()
  if (!user) return
  permissions.value = user.permissions || []
  if (!menuItems.value.length) {
    openTasks.value = []
    dash.value = {}
    return
  }
  try {
    dash.value = await dashboardApi.stats()
    if (canListTasks.value) {
      const tasksRes = await crmApi.listTasks({ status: 'open', page: 1, page_size: 5 })
      const items = tasksRes?.items || []
      openTasks.value = items.map((task) => ({
        id: task.id,
        title: task.title,
        dueLabel: formatDue(task.due_at),
        statusLabel: taskStatusMap[task.status] || task.status,
      }))
    } else {
      openTasks.value = []
    }
  } catch {
    /* ignore */
  }
}

function go(url) {
  uni.navigateTo({ url })
}

onShow(loadData)
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 24rpx;
}

.banner {
  background: linear-gradient(135deg, #1677ff, #0958d9);
  padding: 48rpx 32rpx 64rpx;
  color: #fff;
}

.banner__title {
  display: block;
  font-size: 40rpx;
  font-weight: 600;
  margin-bottom: 8rpx;
}

.banner__sub {
  font-size: 26rpx;
  opacity: 0.9;
}

.cards {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  padding: 0 24rpx;
  margin-top: -40rpx;
}

.card {
  flex: 1 1 calc(33.33% - 12rpx);
  min-width: 200rpx;
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.06);
}

.card--warn .card__value {
  color: #ff4d4f;
}

.card__label {
  display: block;
  font-size: 22rpx;
  color: #666;
  margin-bottom: 8rpx;
}

.card__value {
  display: block;
  font-size: 44rpx;
  font-weight: 600;
  color: #1677ff;
  margin-bottom: 6rpx;
}

.card__hint {
  font-size: 20rpx;
  color: #999;
}

.section {
  margin: 24rpx;
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}

.section__title {
  font-size: 30rpx;
  font-weight: 600;
}

.section__link {
  font-size: 24rpx;
  color: #1677ff;
}

.grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.grid-item {
  flex: 1 1 calc(50% - 8rpx);
  background: #f5f9ff;
  border: 1rpx solid #d6e8ff;
  border-radius: 12rpx;
  padding: 28rpx 24rpx;
}

.grid-item__title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: #1677ff;
  margin-bottom: 8rpx;
}

.grid-item__desc {
  font-size: 24rpx;
  color: #666;
}

.list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
}

.list-item:last-child {
  border-bottom: none;
}

.list-item__title {
  display: block;
  font-size: 28rpx;
  font-weight: 500;
  margin-bottom: 6rpx;
}

.list-item__sub {
  font-size: 24rpx;
  color: #999;
}

.list-item__badge {
  font-size: 22rpx;
  color: #1677ff;
  background: #e6f4ff;
  padding: 6rpx 16rpx;
  border-radius: 8rpx;
}

.empty-page {
  margin: 48rpx 32rpx;
  padding: 48rpx 32rpx;
  background: #fff;
  border-radius: 16rpx;
  text-align: center;
}

.empty-page__title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  margin-bottom: 12rpx;
}

.empty-page__sub {
  font-size: 26rpx;
  color: #999;
}
</style>
