<template>
  <view class="page">
    <view v-if="loading" class="empty">加载中...</view>
    <view v-else-if="!todos.length" class="empty">暂无待审核内容</view>

    <view v-for="item in todos" :key="item.id" class="todo-card">
      <view class="todo-card__header">
        <text class="todo-card__title">{{ item.title }}</text>
        <text class="todo-card__tag">{{ item.platform }}</text>
      </view>
      <text class="todo-card__meta">{{ item.author }} · {{ item.time }}</text>
      <view class="todo-card__actions">
        <button class="btn btn--reject" size="mini" :disabled="acting" @click="handleReject(item)">
          驳回
        </button>
        <button class="btn btn--approve" size="mini" :disabled="acting" @click="handleApprove(item)">
          通过
        </button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { onShow } from '@dcloudio/uni-app'
import { ref } from 'vue'

import { contentApi } from '@/utils/api'
import { getToken } from '@/utils/auth'

const loading = ref(false)
const acting = ref(false)
const todos = ref([])

const platformMap = {
  wechat: '公众号',
  xhs: '小红书',
  douyin: '抖音',
}

function formatTime(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}小时前`
  return new Date(iso).toLocaleDateString('zh-CN')
}

async function loadTodos() {
  if (!getToken()) {
    todos.value = []
    return
  }
  loading.value = true
  try {
    const data = await contentApi.list({ status: 'pending_review', page_size: 50 })
    todos.value = data.items.map((item) => ({
      id: item.id,
      title: item.topic,
      platform: platformMap[item.platform] || item.platform,
      author: item.author_name || '—',
      time: formatTime(item.updated_at || item.created_at),
    }))
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function handleApprove(item) {
  acting.value = true
  try {
    await contentApi.approve(item.id)
    uni.showToast({ title: '已通过', icon: 'success' })
    loadTodos()
  } catch (e) {
    uni.showToast({ title: e.message || '操作失败', icon: 'none' })
  } finally {
    acting.value = false
  }
}

async function handleReject(item) {
  acting.value = true
  try {
    await contentApi.reject(item.id)
    uni.showToast({ title: '已驳回', icon: 'none' })
    loadTodos()
  } catch (e) {
    uni.showToast({ title: e.message || '操作失败', icon: 'none' })
  } finally {
    acting.value = false
  }
}

onShow(loadTodos)
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 24rpx;
}

.empty {
  text-align: center;
  color: #999;
  padding: 80rpx 0;
  font-size: 28rpx;
}

.todo-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.todo-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12rpx;
}

.todo-card__title {
  font-size: 30rpx;
  font-weight: 600;
  flex: 1;
  padding-right: 16rpx;
}

.todo-card__tag {
  font-size: 22rpx;
  color: #1677ff;
  background: #e6f4ff;
  padding: 4rpx 12rpx;
  border-radius: 6rpx;
}

.todo-card__meta {
  font-size: 24rpx;
  color: #999;
  display: block;
  margin-bottom: 20rpx;
}

.todo-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: 16rpx;
}

.btn {
  font-size: 26rpx;
  border-radius: 8rpx;
}

.btn--reject {
  background: #fff;
  color: #666;
  border: 1rpx solid #d9d9d9;
}

.btn--approve {
  background: #1677ff;
  color: #fff;
}
</style>
