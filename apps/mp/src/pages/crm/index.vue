<template>
  <view class="page">
    <view class="banner">
      <text class="banner__title">销售管理</text>
      <text class="banner__sub">线索 · 客户 · 商机 · 订单</text>
    </view>

    <view v-if="!menuItems.length" class="empty-page">
      <text class="empty-page__title">暂无销售模块权限</text>
      <text class="empty-page__sub">请联系管理员开通线索、客户、商机或订单权限</text>
    </view>

    <template v-else>
      <view v-if="showAmountBoard" class="amt-cards">
        <view class="amt-card" @click="go('/pages/crm/deals')">
          <text class="amt-card__label">本月目标</text>
          <text class="amt-card__value">{{ formatCompactMoney(amountBoard.target) }}</text>
          <text class="amt-card__hint">{{ monthEndLabel() }}</text>
        </view>
        <view class="amt-card" @click="go('/pages/crm/deals')">
          <text class="amt-card__label">预测成交</text>
          <text class="amt-card__value accent">{{ formatCompactMoney(amountBoard.completed) }}</text>
          <text class="amt-card__hint">完成率 {{ amountBoard.rate }}%</text>
        </view>
        <view class="amt-card" @click="go('/pages/crm/payments')">
          <text class="amt-card__label">本月回款</text>
          <text class="amt-card__value success">{{ formatCompactMoney(amountBoard.payments) }}</text>
          <text class="amt-card__hint">{{ amountBoard.paymentCount }}笔已到账</text>
        </view>
      </view>

      <view v-if="funnelStages.length" class="section">
        <view class="section__header">
          <text class="section__title">📊 销售漏斗</text>
          <text class="section__link" @click="go('/pages/crm/deals')">详情 ›</text>
        </view>
        <view class="funnel-row">
          <view v-for="stage in funnelStages" :key="stage.stage_id" class="funnel-stage">
            <text class="funnel-stage__num">{{ stage.deal_count }}</text>
            <text class="funnel-stage__label">{{ stage.stage_name }}</text>
          </view>
        </view>
        <text v-if="funnelTotal" class="funnel-hint">在途商机 {{ funnelTotal }} 个</text>
      </view>

      <view class="section">
        <view class="section__header">
          <text class="section__title">☰ 功能入口</text>
        </view>
        <view class="feat-grid">
          <view v-for="item in menuItems" :key="item.url" class="feat-item" @click="go(item.url)">
            <view class="feat-icon" :style="{ color: item.iconColor }">{{ item.icon }}</view>
            <view class="feat-text">
              <text class="feat-title">{{ item.title }}</text>
              <text class="feat-desc">{{ item.desc }}</text>
            </view>
          </view>
        </view>
      </view>

      <view v-if="openTasks.length" class="section">
        <view class="section__header">
          <text class="section__title">📋 待办任务</text>
          <text class="section__link" @click="go('/pages/crm/tasks')">查看全部 ›</text>
        </view>
        <view v-for="task in openTasks" :key="task.id" class="task-item" @click="go('/pages/crm/tasks')">
          <view class="task-priority" :class="task.priorityClass" />
          <view class="task-content">
            <text class="task-title">{{ task.title }}</text>
            <text class="task-meta">{{ task.dueLabel }}</text>
          </view>
          <text class="task-badge" :class="task.badgeClass">{{ task.statusLabel }}</text>
        </view>
      </view>

      <view v-if="recentActivities.length" class="section">
        <view class="section__header">
          <text class="section__title">💬 最近跟进</text>
          <text class="section__link" @click="go('/pages/crm/leads')">全部 ›</text>
        </view>
        <view v-for="act in recentActivities" :key="act.id" class="act-item" @click="go(act.url)">
          <view class="act-avatar">{{ act.avatar }}</view>
          <view class="act-content">
            <text class="act-text">{{ act.text }}</text>
            <text class="act-time">{{ act.time }}</text>
          </view>
        </view>
      </view>
    </template>

    <view v-if="menuItems.length && showFab" class="fab" @click="openFab">+</view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import { analyticsApi, crmApi } from '@/utils/api'
import {
  calcProgress,
  deriveSalesTarget,
  formatCompactMoney,
  formatRelativeTime,
  isThisMonth,
  monthEndLabel,
} from '@/utils/h5Format'
import { CRM_MENU, filterMenuByPermission, hasAnyPermission, hasPermission } from '@/utils/permissions'
import { formatDueAtRelative } from '@/utils/taskMeta'
import { ensureSession } from '@/utils/session'

const permissions = ref([])
const amountBoard = ref({ target: 0, completed: 0, rate: 0, payments: 0, paymentCount: 0 })
const funnelStages = ref([])
const funnelTotal = ref(0)
const openTasks = ref([])
const recentActivities = ref([])

const menuItems = computed(() => filterMenuByPermission(CRM_MENU, permissions.value))

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

const canListPayments = computed(() =>
  hasAnyPermission(permissions.value, [
    'crm.payment.list_own',
    'crm.payment.list_team',
    'crm.payment.list_territory',
    'crm.payment.list_all',
  ]),
)

const canCreateLead = computed(() => hasPermission(permissions.value, 'crm.lead.create'))
const canCreateActivity = computed(() => hasPermission(permissions.value, 'crm.activity.create'))
const canCreatePayment = computed(() => hasPermission(permissions.value, 'crm.payment.create'))

const showAmountBoard = computed(() => canListDeals.value || canListPayments.value)
const showFab = computed(() => canCreateLead.value || canCreateActivity.value || canCreatePayment.value)

const taskStatusMap = {
  open: '待办',
  in_progress: '进行中',
  on_hold: '已挂起',
  done: '已完成',
  cancelled: '已取消',
}

function priorityClass(priority) {
  if (priority === 'high') return 'high'
  if (priority === 'low') return 'low'
  return 'medium'
}

function pickFunnelStages(stages) {
  if (!stages?.length) return []
  const visible = stages.filter((s) => !s.is_lost_stage)
  if (visible.length <= 4) return visible
  return visible.slice(0, 4)
}

async function loadAmountBoard() {
  let weighted = 0
  let wonAmount = 0
  if (canListDeals.value) {
    try {
      const forecast = await analyticsApi.dealForecast()
      weighted = forecast?.weighted_amount ?? 0
      const wonRes = await crmApi.listDeals({ status: 'won', page: 1, page_size: 50 })
      for (const deal of wonRes?.items || []) {
        if (isThisMonth(deal.closed_at)) wonAmount += Number(deal.amount) || 0
      }
    } catch {
      /* ignore */
    }
  }
  const target = deriveSalesTarget(weighted, wonAmount)
  const completed = weighted
  const rate = calcProgress(completed, target)

  let payments = 0
  let paymentCount = 0
  if (canListPayments.value) {
    try {
      const payRes = await crmApi.listPayments({ status: 'confirmed', page: 1, page_size: 50 })
      for (const p of payRes?.items || []) {
        if (isThisMonth(p.paid_at)) {
          payments += Number(p.amount) || 0
          paymentCount += 1
        }
      }
    } catch {
      /* ignore */
    }
  }
  amountBoard.value = { target, completed, rate, payments, paymentCount }
}

async function loadFunnel() {
  if (!canListDeals.value) {
    funnelStages.value = []
    funnelTotal.value = 0
    return
  }
  try {
    const stages = await analyticsApi.dealFunnel()
    funnelStages.value = pickFunnelStages(stages)
    funnelTotal.value = (stages || []).reduce((sum, s) => sum + (s.deal_count || 0), 0)
  } catch {
    funnelStages.value = []
    funnelTotal.value = 0
  }
}

async function loadTasks() {
  if (!canListTasks.value) {
    openTasks.value = []
    return
  }
  try {
    const tasksRes = await crmApi.listTasks({ page: 1, page_size: 5 })
    const items = (tasksRes?.items || []).filter((t) => t.status === 'open' || t.status === 'in_progress')
    openTasks.value = items.slice(0, 5).map((task) => {
      const overdue = task.due_at && new Date(task.due_at) < new Date()
      return {
        id: task.id,
        title: task.title,
        dueLabel: `截止：${formatDueAtRelative(task.due_at)}`,
        statusLabel: overdue ? '已逾期' : taskStatusMap[task.status] || task.status,
        badgeClass: overdue ? 'warn' : 'open',
        priorityClass: priorityClass(task.priority),
      }
    })
  } catch {
    openTasks.value = []
  }
}

async function loadRecentActivities() {
  if (!canCreateActivity.value) {
    recentActivities.value = []
    return
  }
  try {
    const fetches = []
    const canLeads = hasAnyPermission(permissions.value, [
      'crm.lead.list_own',
      'crm.lead.list_team',
      'crm.lead.list_territory',
      'crm.lead.list_all',
    ])
    if (canLeads) {
      const leadsRes = await crmApi.listLeads({ page: 1, page_size: 3 })
      for (const lead of (leadsRes?.items || []).slice(0, 2)) {
        fetches.push(
          crmApi.listActivities({ lead_id: lead.id }).then((items) =>
            (items || []).map((a) => ({
              ...a,
              entityName: lead.name || lead.company_name || '线索',
              url: `/pages/crm/lead-detail?id=${lead.id}`,
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
              url: `/pages/crm/deal-detail?id=${deal.id}`,
            })),
          ),
        )
      }
    }
    const merged = (await Promise.all(fetches)).flat()
    recentActivities.value = merged
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      .slice(0, 5)
      .map((a) => ({
        id: a.id,
        avatar: (a.entityName || '跟').slice(0, 1),
        text: `${a.entityName}：${(a.content || a.subject || '跟进记录').slice(0, 40)}`,
        time: formatRelativeTime(a.created_at),
        url: a.url,
      }))
  } catch {
    recentActivities.value = []
  }
}

async function loadData() {
  const user = await ensureSession()
  if (!user) return
  permissions.value = user.permissions || []
  if (!menuItems.value.length) {
    amountBoard.value = { target: 0, completed: 0, rate: 0, payments: 0, paymentCount: 0 }
    funnelStages.value = []
    openTasks.value = []
    recentActivities.value = []
    return
  }
  await Promise.all([loadAmountBoard(), loadFunnel(), loadTasks(), loadRecentActivities()])
}

function go(url) {
  uni.navigateTo({ url })
}

function openFab() {
  const items = []
  const actions = []
  if (canCreateLead.value) {
    items.push('新建线索')
    actions.push(() => uni.navigateTo({ url: '/pages/crm/lead-create' }))
  }
  if (canCreateActivity.value) {
    items.push('写跟进')
    actions.push(() => uni.navigateTo({ url: '/pages/crm/leads' }))
  }
  if (canCreatePayment.value) {
    items.push('登记回款')
    actions.push(() => uni.navigateTo({ url: '/pages/crm/payments' }))
  }
  if (!items.length) return
  uni.showActionSheet({
    itemList: items,
    success(res) {
      actions[res.tapIndex]?.()
    },
  })
}

onShow(loadData)
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f0f2f5;
  padding-bottom: 120rpx;
}

.banner {
  background: linear-gradient(135deg, #1677ff, #0958d9);
  padding: 48rpx 32rpx 96rpx;
  color: #fff;
}

.banner__title {
  display: block;
  font-size: 40rpx;
  font-weight: 700;
  margin-bottom: 8rpx;
}

.banner__sub {
  font-size: 26rpx;
  opacity: 0.9;
}

.amt-cards {
  display: flex;
  gap: 16rpx;
  padding: 0 24rpx;
  margin-top: -72rpx;
  position: relative;
  z-index: 2;
}

.amt-card {
  flex: 1;
  background: #fff;
  border-radius: 20rpx;
  padding: 24rpx 16rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.06);
  text-align: center;
}

.amt-card__label {
  display: block;
  font-size: 22rpx;
  color: #666;
  margin-bottom: 8rpx;
}

.amt-card__value {
  display: block;
  font-size: 36rpx;
  font-weight: 700;
  color: #1f1f1f;
  margin-bottom: 6rpx;
}

.amt-card__value.accent {
  color: #1677ff;
}

.amt-card__value.success {
  color: #52c41a;
}

.amt-card__hint {
  font-size: 20rpx;
  color: #999;
}

.section {
  margin: 24rpx;
  background: #fff;
  border-radius: 20rpx;
  padding: 24rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.04);
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

.funnel-row {
  display: flex;
  gap: 12rpx;
  margin-bottom: 12rpx;
}

.funnel-stage {
  flex: 1;
  text-align: center;
  padding: 16rpx 8rpx;
  border-radius: 12rpx;
  background: #e6f4ff;
}

.funnel-stage__num {
  display: block;
  font-size: 32rpx;
  font-weight: 700;
  color: #1677ff;
  margin-bottom: 4rpx;
}

.funnel-stage__label {
  font-size: 20rpx;
  color: #666;
}

.funnel-hint {
  font-size: 24rpx;
  color: #999;
}

.feat-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16rpx;
}

.feat-item {
  background: #e6f4ff;
  border: 1rpx solid #d6e8ff;
  border-radius: 16rpx;
  padding: 24rpx;
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.feat-icon {
  width: 72rpx;
  height: 72rpx;
  border-radius: 16rpx;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36rpx;
  flex-shrink: 0;
}

.feat-text {
  flex: 1;
  min-width: 0;
}

.feat-title {
  display: block;
  font-size: 30rpx;
  font-weight: 700;
  color: #1677ff;
  margin-bottom: 4rpx;
}

.feat-desc {
  font-size: 24rpx;
  color: #666;
}

.task-item {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding: 20rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
}

.task-item:last-child {
  border-bottom: none;
}

.task-priority {
  width: 8rpx;
  height: 72rpx;
  border-radius: 4rpx;
  flex-shrink: 0;
  margin-top: 4rpx;
}

.task-priority.high {
  background: #ff4d4f;
}

.task-priority.medium {
  background: #fa8c16;
}

.task-priority.low {
  background: #52c41a;
}

.task-content {
  flex: 1;
  min-width: 0;
}

.task-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  margin-bottom: 6rpx;
}

.task-meta {
  font-size: 22rpx;
  color: #999;
}

.task-badge {
  font-size: 22rpx;
  padding: 6rpx 16rpx;
  border-radius: 8rpx;
  white-space: nowrap;
}

.task-badge.open {
  color: #1677ff;
  background: #e6f4ff;
}

.task-badge.warn {
  color: #ff4d4f;
  background: #fff2f0;
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

.fab {
  position: fixed;
  right: 32rpx;
  bottom: 140rpx;
  width: 96rpx;
  height: 96rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #1677ff, #0958d9);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48rpx;
  box-shadow: 0 8rpx 24rpx rgba(22, 119, 255, 0.35);
  z-index: 100;
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
