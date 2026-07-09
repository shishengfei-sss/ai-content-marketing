<template>
  <view class="page">
    <view class="banner">
      <text class="banner__title">智营获客</text>
      <text class="banner__sub">AI 内容营销 · 销售管理</text>
    </view>

    <view class="cards">
      <view class="card card--primary" @click="goDrafts">
        <text class="card__label">我的内容</text>
        <text class="card__value">{{ stats.drafts }}</text>
        <text class="card__hint">点击查看内容箱</text>
      </view>
      <view class="card" @click="goSchedule">
        <text class="card__label">今日排期</text>
        <text class="card__value">{{ stats.scheduled }}</text>
        <text class="card__hint">公众号自动发布</text>
      </view>
    </view>

    <view v-if="showCrm" class="section section--crm">
      <view class="section__header">
        <text class="section__title">销售概览</text>
        <text class="section__link" @click="goCrmHub">进入销售</text>
      </view>
      <view class="crm-cards">
        <view v-if="canListLeads" class="crm-card" @click="goLeads">
          <text class="crm-card__value">{{ stats.crmNewLeads }}</text>
          <text class="crm-card__label">近7日新线索</text>
        </view>
        <view v-if="canListTasks" class="crm-card" @click="goTasks">
          <text class="crm-card__value">{{ stats.crmTasksDue }}</text>
          <text class="crm-card__label">今日待办</text>
        </view>
        <view v-if="canListTasks" class="crm-card" :class="{ 'crm-card--warn': stats.crmTasksOverdue > 0 }" @click="goTasks">
          <text class="crm-card__value">{{ stats.crmTasksOverdue }}</text>
          <text class="crm-card__label">逾期任务</text>
        </view>
      </view>
      <view class="crm-actions">
        <view v-if="canListLeads" class="crm-action" @click="goLeads">线索</view>
        <view v-if="canListCustomers" class="crm-action" @click="goCustomers">客户</view>
        <view v-if="canListTasks" class="crm-action" @click="goTasks">任务</view>
      </view>
    </view>

    <view class="section">
      <view class="section__header">
        <text class="section__title">今日排期</text>
      </view>
      <view v-if="!schedule.length" class="empty">暂无排期</view>
      <view v-for="item in schedule" :key="item.id" class="list-item">
        <view class="list-item__main">
          <text class="list-item__title">{{ item.title }}</text>
          <text class="list-item__sub">{{ item.time }} · {{ item.platform }}</text>
        </view>
        <text class="list-item__badge">{{ item.status }}</text>
      </view>
    </view>

    <view class="section">
      <view class="section__header">
        <text class="section__title">快捷操作</text>
      </view>
      <view class="actions">
        <view class="action-btn" @click="goCreate">新建创作</view>
        <view v-if="canListLeads" class="action-btn action-btn--outline" @click="goLeads">我的线索</view>
        <view v-if="canListTasks" class="action-btn action-btn--outline" @click="goTasks">今日任务</view>
        <view v-if="!canListLeads && !canListTasks" class="action-btn action-btn--outline" @click="goContents">内容库</view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import { contentApi, dashboardApi } from '@/utils/api'
import { hasAnyCrmListPermission, hasAnyPermission } from '@/utils/permissions'
import { ensureSession } from '@/utils/session'

const permissions = ref([])
const stats = ref({
  drafts: 0,
  scheduled: 0,
  crmNewLeads: 0,
  crmTasksDue: 0,
  crmTasksOverdue: 0,
})
const schedule = ref([])

const platformMap = { wechat: '公众号', xhs: '小红书', douyin: '抖音' }
const statusMap = { scheduled: '已排期', published: '已发布' }

const showCrm = computed(() => hasAnyCrmListPermission(permissions.value))
const canListLeads = computed(() =>
  hasAnyPermission(permissions.value, [
    'crm.lead.list_own',
    'crm.lead.list_team',
    'crm.lead.list_territory',
    'crm.lead.list_all',
  ]),
)
const canListCustomers = computed(() =>
  hasAnyPermission(permissions.value, [
    'crm.customer.list_own',
    'crm.customer.list_team',
    'crm.customer.list_territory',
    'crm.customer.list_all',
  ]),
)
const canListTasks = computed(() =>
  hasAnyPermission(permissions.value, [
    'crm.task.list_own',
    'crm.task.list_team',
    'crm.task.list_territory',
    'crm.task.list_all',
  ]),
)

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

async function loadData() {
  const user = await ensureSession()
  if (!user) return
  permissions.value = user.permissions || []
  try {
    const [dash, cal] = await Promise.all([dashboardApi.stats(), contentApi.calendar()])
    stats.value = {
      drafts: dash.draft_count ?? 0,
      scheduled: dash.today_scheduled,
      crmNewLeads: dash.crm_new_leads ?? 0,
      crmTasksDue: dash.crm_tasks_due_today ?? 0,
      crmTasksOverdue: dash.crm_tasks_overdue ?? 0,
    }
    schedule.value = cal.slice(0, 5).map((item) => ({
      id: item.id,
      title: item.title,
      time: formatTime(item.scheduled_at),
      platform: platformMap[item.platform] || item.platform,
      status: statusMap[item.status] || item.status,
    }))
  } catch {
    /* ignore */
  }
}

function goDrafts() {
  uni.switchTab({ url: '/pages/todo/todo' })
}
function goCreate() {
  uni.switchTab({ url: '/pages/create/create' })
}
function goContents() {
  uni.showToast({ title: '请使用 Web 内容库', icon: 'none' })
}
function goCrmHub() {
  uni.switchTab({ url: '/pages/crm/index' })
}
function goLeads() {
  uni.navigateTo({ url: '/pages/crm/leads' })
}
function goCustomers() {
  uni.navigateTo({ url: '/pages/crm/customers' })
}
function goTasks() {
  uni.navigateTo({ url: '/pages/crm/tasks' })
}
function goSchedule() {
  uni.switchTab({ url: '/pages/todo/todo' })
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
  opacity: 0.85;
}

.cards {
  display: flex;
  gap: 24rpx;
  padding: 0 24rpx;
  margin-top: -40rpx;
}

.card {
  flex: 1;
  background: #fff;
  border-radius: 16rpx;
  padding: 28rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.06);
}

.card--primary .card__value {
  color: #1677ff;
}

.card__label {
  display: block;
  font-size: 24rpx;
  color: #666;
  margin-bottom: 8rpx;
}

.card__value {
  display: block;
  font-size: 48rpx;
  font-weight: 600;
  margin-bottom: 8rpx;
}

.card__hint {
  font-size: 22rpx;
  color: #999;
}

.section {
  margin: 24rpx;
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.section--crm {
  border-top: 4rpx solid #1677ff;
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

.crm-cards {
  display: flex;
  gap: 16rpx;
  margin-bottom: 16rpx;
}

.crm-card {
  flex: 1;
  background: #f5f9ff;
  border-radius: 12rpx;
  padding: 20rpx 16rpx;
  text-align: center;
}

.crm-card--warn .crm-card__value {
  color: #ff4d4f;
}

.crm-card__value {
  display: block;
  font-size: 40rpx;
  font-weight: 600;
  color: #1677ff;
  margin-bottom: 6rpx;
}

.crm-card__label {
  font-size: 22rpx;
  color: #666;
}

.crm-actions {
  display: flex;
  gap: 12rpx;
}

.crm-action {
  flex: 1;
  text-align: center;
  padding: 16rpx 0;
  border-radius: 10rpx;
  font-size: 26rpx;
  color: #1677ff;
  background: #e6f4ff;
}

.empty {
  color: #999;
  font-size: 26rpx;
  padding: 16rpx 0;
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

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.action-btn {
  flex: 1 1 calc(50% - 8rpx);
  text-align: center;
  background: #1677ff;
  color: #fff;
  padding: 20rpx;
  border-radius: 12rpx;
  font-size: 28rpx;
}

.action-btn--outline {
  background: #fff;
  color: #1677ff;
  border: 1rpx solid #91caff;
}
</style>
