<template>
  <view class="page">
    <view class="banner">
      <text class="banner__title">智营获客</text>
      <text class="banner__sub">AI 内容营销</text>
    </view>

    <view class="cards">
      <view class="card card--primary" @click="goDrafts">
        <text class="card__label">我的内容</text>
        <text class="card__value">{{ stats.drafts }}</text>
        <text class="card__hint">点击查看内容箱</text>
      </view>
      <view class="card">
        <text class="card__label">今日排期</text>
        <text class="card__value">{{ stats.scheduled }}</text>
        <text class="card__hint">公众号自动发布</text>
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
        <view class="action-btn action-btn--outline" @click="goContents">内容库</view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import { contentApi, dashboardApi } from '@/utils/api'
import { getToken } from '@/utils/auth'

const stats = ref({ drafts: 0, scheduled: 0 })
const schedule = ref([])

const platformMap = { wechat: '公众号', xhs: '小红书', douyin: '抖音' }
const statusMap = { scheduled: '已排期', published: '已发布' }

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

async function loadData() {
  if (!getToken()) return
  try {
    const [dash, cal] = await Promise.all([dashboardApi.stats(), contentApi.calendar()])
    stats.value = {
      drafts: dash.draft_count ?? 0,
      scheduled: dash.today_scheduled,
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

.section__header {
  margin-bottom: 16rpx;
}

.section__title {
  font-size: 30rpx;
  font-weight: 600;
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
  gap: 16rpx;
}

.action-btn {
  flex: 1;
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
  border: 1rpx solid #1677ff;
}
</style>
