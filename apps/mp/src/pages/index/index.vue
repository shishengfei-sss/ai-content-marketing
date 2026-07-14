<template>
  <view class="page">
    <view class="banner">
      <view class="banner-top">
        <view class="search" @click="goSearch">
          <text class="search__icon">🔍</text>
          <text class="search__text">搜索线索、客户、内容</text>
        </view>
        <view class="bell" @click="goNotifications">
          <text>🔔</text>
          <view v-if="stats.crmTasksOverdue > 0" class="bell__dot" />
        </view>
      </view>
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

    <view v-if="showCrm && showPerformance" class="section">
      <view class="section__header">
        <text class="section__title">📈 本月业绩</text>
        <text class="section__link" @click="goCrmHub">详情 ›</text>
      </view>
      <view class="perf-row">
        <view class="perf-icon blue">💰</view>
        <view class="perf-info">
          <text class="perf-label">预测成交</text>
          <text class="perf-desc">完成 {{ perfSales.rate }}% · 剩余 {{ daysLeftInMonth() }} 天</text>
          <view class="perf-bar">
            <view class="perf-bar-inner" :style="{ width: perfSales.rate + '%' }" />
          </view>
        </view>
        <text class="perf-value">{{ formatCompactMoney(perfSales.current) }}</text>
      </view>
      <view class="perf-row">
        <view class="perf-icon green">📱</view>
        <view class="perf-info">
          <text class="perf-label">新增线索</text>
          <text class="perf-desc">近7日 {{ stats.crmNewLeads }} 个 · 目标 {{ perfLeads.target }} 个</text>
          <view class="perf-bar">
            <view class="perf-bar-inner perf-bar-inner--green" :style="{ width: perfLeads.rate + '%' }" />
          </view>
        </view>
        <text class="perf-value perf-value--green">{{ stats.crmNewLeads }}</text>
      </view>
    </view>

    <view v-if="showCrm" class="section section--crm">
      <view class="section__header">
        <text class="section__title">💼 销售概览</text>
        <text class="section__link" @click="goCrmHub">进入销售 ›</text>
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
        <view
          v-if="canListTasks"
          class="crm-card"
          :class="{ 'crm-card--warn': stats.crmTasksOverdue > 0 }"
          @click="goTasks"
        >
          <text class="crm-card__value">{{ stats.crmTasksOverdue }}</text>
          <text class="crm-card__label">逾期任务</text>
        </view>
      </view>
    </view>

    <view class="section">
      <view class="section__header">
        <text class="section__title">⚡ 快捷操作</text>
      </view>
      <view class="qa-grid">
        <view v-for="action in quickActions" :key="action.key" class="qa-item" @click="action.onClick">
          <view class="qa-icon" :class="action.color">{{ action.icon }}</view>
          <text class="qa-label">{{ action.label }}</text>
        </view>
      </view>
    </view>

    <view class="section">
      <view class="section__header">
        <text class="section__title">📅 今日排期</text>
        <text class="section__link" @click="goDrafts">全部 ›</text>
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

    <view v-if="recentActivities.length" class="section">
      <view class="section__header">
        <text class="section__title">🔄 最近动态</text>
      </view>
      <view v-for="act in recentActivities" :key="act.id" class="act-item" @click="act.onClick?.()">
        <view class="act-avatar">{{ act.avatar }}</view>
        <view class="act-content">
          <text class="act-text">{{ act.text }}</text>
          <text class="act-time">{{ act.time }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import { analyticsApi, contentApi, crmApi, dashboardApi } from '@/utils/api'
import {
  calcProgress,
  daysLeftInMonth,
  deriveSalesTarget,
  formatCompactMoney,
  formatRelativeTime,
} from '@/utils/h5Format'
import { hasAnyCrmListPermission, hasAnyPermission, hasPermission } from '@/utils/permissions'
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
const perfSales = ref({ current: 0, target: 0, rate: 0 })
const recentActivities = ref([])

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
const canListDeals = computed(() =>
  hasAnyPermission(permissions.value, [
    'crm.deal.list_own',
    'crm.deal.list_team',
    'crm.deal.list_territory',
    'crm.deal.list_all',
  ]),
)
const canListQuotes = computed(() =>
  hasAnyPermission(permissions.value, ['crm.quote.list_own', 'crm.quote.list_all']),
)
const canCreateActivity = computed(() => hasPermission(permissions.value, 'crm.activity.create'))
const canCreateLead = computed(() => hasPermission(permissions.value, 'crm.lead.create'))

const showPerformance = computed(() => canListDeals.value || canListLeads.value)

const perfLeads = computed(() => {
  const target = 10
  const current = stats.value.crmNewLeads
  return { target, current, rate: calcProgress(current, target) }
})

const quickActions = computed(() => {
  const items = [
    { key: 'create', label: '新建创作', icon: '✎', color: 'blue', onClick: goCreate },
  ]
  if (canListLeads.value) {
    items.push({ key: 'leads', label: '我的线索', icon: '👤', color: 'green', onClick: goLeads })
  }
  if (canListTasks.value) {
    items.push({ key: 'tasks', label: '今日任务', icon: '📋', color: 'orange', onClick: goTasks })
  }
  if (canListCustomers.value) {
    items.push({ key: 'customers', label: '客户拜访', icon: '👥', color: 'red', onClick: goCustomers })
  }
  if (canCreateActivity.value) {
    items.push({ key: 'activity', label: '写跟进', icon: '💬', color: 'blue', onClick: goLeads })
  }
  if (showCrm.value) {
    items.push({ key: 'crm', label: '数据看板', icon: '📈', color: 'green', onClick: goCrmHub })
  }
  if (canListQuotes.value) {
    items.push({ key: 'quotes', label: '新建报价', icon: '📄', color: 'orange', onClick: goQuotes })
  }
  items.push({ key: 'contents', label: '内容库', icon: '🗂️', color: 'blue', onClick: goContents })
  return items.slice(0, 8)
})

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

async function loadPerformance() {
  if (!canListDeals.value) {
    perfSales.value = { current: 0, target: 0, rate: 0 }
    return
  }
  try {
    const forecast = await analyticsApi.dealForecast()
    const current = forecast?.weighted_amount ?? 0
    const target = deriveSalesTarget(current, 0)
    perfSales.value = { current, target, rate: calcProgress(current, target) }
  } catch {
    perfSales.value = { current: 0, target: 0, rate: 0 }
  }
}

async function loadRecentActivities() {
  if (!canCreateActivity.value) {
    recentActivities.value = []
    return
  }
  try {
    const fetches = []
    if (canListLeads.value) {
      const leadsRes = await crmApi.listLeads({ page: 1, page_size: 3 })
      for (const lead of (leadsRes?.items || []).slice(0, 2)) {
        fetches.push(
          crmApi.listActivities({ lead_id: lead.id }).then((items) =>
            (items || []).map((a) => ({
              ...a,
              entityName: lead.name || lead.company_name || '线索',
              onClick: () => uni.navigateTo({ url: `/pages/crm/lead-detail?id=${lead.id}` }),
            })),
          ),
        )
      }
    }
    if (canListDeals.value) {
      const dealsRes = await crmApi.listDeals({ page: 1, page_size: 3, status: 'open' })
      for (const deal of (dealsRes?.items || []).slice(0, 2)) {
        fetches.push(
          crmApi.listDealActivities(deal.id).then((items) =>
            (items || []).map((a) => ({
              ...a,
              entityName: deal.name || '商机',
              onClick: () => uni.navigateTo({ url: `/pages/crm/deal-detail?id=${deal.id}` }),
            })),
          ),
        )
      }
    }
    const merged = (await Promise.all(fetches)).flat()
    recentActivities.value = merged
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      .slice(0, 3)
      .map((a) => ({
        id: a.id,
        avatar: (a.entityName || '动').slice(0, 1),
        text: `${a.entityName}：${(a.content || a.subject || '有新的跟进').slice(0, 36)}`,
        time: formatRelativeTime(a.created_at),
        onClick: a.onClick,
      }))
  } catch {
    recentActivities.value = []
  }
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
  await Promise.all([loadPerformance(), loadRecentActivities()])
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
function goQuotes() {
  uni.navigateTo({ url: '/pages/crm/quotes' })
}
function goSchedule() {
  uni.switchTab({ url: '/pages/todo/todo' })
}
function goSearch() {
  if (canListLeads.value) {
    uni.navigateTo({ url: '/pages/crm/leads' })
    return
  }
  if (canListCustomers.value) {
    uni.navigateTo({ url: '/pages/crm/customers' })
    return
  }
  uni.showToast({ title: '暂无搜索权限', icon: 'none' })
}
function goNotifications() {
  if (canListTasks.value) {
    goTasks()
    return
  }
  uni.showToast({ title: '暂无待办提醒', icon: 'none' })
}

onShow(loadData)
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f0f2f5;
  padding-bottom: 24rpx;
}

.banner {
  background: linear-gradient(135deg, #1677ff, #0958d9);
  padding: 24rpx 32rpx 72rpx;
  color: #fff;
}

.banner-top {
  display: flex;
  align-items: center;
  margin-bottom: 24rpx;
}

.search {
  flex: 1;
  height: 72rpx;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 36rpx;
  display: flex;
  align-items: center;
  padding: 0 24rpx;
  gap: 10rpx;
}

.search__icon {
  font-size: 28rpx;
}

.search__text {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.85);
}

.bell {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 16rpx;
  position: relative;
  font-size: 32rpx;
}

.bell__dot {
  position: absolute;
  top: 12rpx;
  right: 12rpx;
  width: 16rpx;
  height: 16rpx;
  background: #ff4d4f;
  border-radius: 50%;
  border: 4rpx solid #1677ff;
}

.banner__title {
  display: block;
  font-size: 44rpx;
  font-weight: 700;
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
  margin-top: -48rpx;
  position: relative;
  z-index: 2;
}

.card {
  flex: 1;
  background: #fff;
  border-radius: 20rpx;
  padding: 28rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.06);
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
  font-weight: 700;
  margin-bottom: 8rpx;
}

.card__hint {
  font-size: 22rpx;
  color: #999;
}

.section {
  margin: 24rpx;
  background: #fff;
  border-radius: 20rpx;
  padding: 24rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.04);
}

.section--crm {
  border-left: 6rpx solid #1677ff;
}

.section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}

.section__title {
  font-size: 30rpx;
  font-weight: 700;
}

.section__link {
  font-size: 24rpx;
  color: #1677ff;
}

.perf-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 16rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
}

.perf-row:last-child {
  border-bottom: none;
}

.perf-icon {
  width: 72rpx;
  height: 72rpx;
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
  flex-shrink: 0;
}

.perf-icon.blue {
  background: #e6f4ff;
}

.perf-icon.green {
  background: #f6ffed;
}

.perf-info {
  flex: 1;
  min-width: 0;
}

.perf-label {
  display: block;
  font-size: 26rpx;
  font-weight: 600;
  margin-bottom: 4rpx;
}

.perf-desc {
  display: block;
  font-size: 22rpx;
  color: #999;
}

.perf-bar {
  width: 100%;
  height: 12rpx;
  background: #f0f0f0;
  border-radius: 6rpx;
  margin-top: 10rpx;
  overflow: hidden;
}

.perf-bar-inner {
  height: 100%;
  border-radius: 6rpx;
  background: linear-gradient(90deg, #1677ff, #4096ff);
}

.perf-bar-inner--green {
  background: linear-gradient(90deg, #52c41a, #73d13d);
}

.perf-value {
  font-size: 30rpx;
  font-weight: 700;
  color: #1677ff;
  flex-shrink: 0;
}

.perf-value--green {
  color: #52c41a;
}

.crm-cards {
  display: flex;
  gap: 16rpx;
}

.crm-card {
  flex: 1;
  background: #e6f4ff;
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
  font-weight: 700;
  color: #1677ff;
  margin-bottom: 6rpx;
}

.crm-card__label {
  font-size: 22rpx;
  color: #666;
}

.qa-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20rpx;
}

.qa-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10rpx;
}

.qa-icon {
  width: 88rpx;
  height: 88rpx;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36rpx;
}

.qa-icon.blue {
  background: #e6f4ff;
}

.qa-icon.green {
  background: #f6ffed;
}

.qa-icon.orange {
  background: #fff7e6;
}

.qa-icon.red {
  background: #fff2f0;
}

.qa-label {
  font-size: 22rpx;
  color: #1f1f1f;
  text-align: center;
}

.empty {
  color: #999;
  font-size: 26rpx;
  padding: 16rpx 0;
  text-align: center;
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

.act-item {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding: 20rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
}

.act-item:last-child {
  border-bottom: none;
}

.act-avatar {
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  background: #e6f4ff;
  color: #1677ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  font-weight: 700;
  flex-shrink: 0;
}

.act-content {
  flex: 1;
  min-width: 0;
}

.act-text {
  display: block;
  font-size: 26rpx;
  line-height: 1.5;
  margin-bottom: 4rpx;
}

.act-time {
  font-size: 22rpx;
  color: #999;
}
</style>
