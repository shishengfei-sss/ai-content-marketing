<script setup>
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { agentApi } from '@/utils/api'
import { shouldSilenceLoadError, toastApiError } from '@/utils/apiError'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'

const loading = ref(false)
const activeTab = ref('user')
const userMemories = ref([])
const tenantMemories = ref([])
const isAdmin = ref(false)

const pendingMemories = computed(() =>
  userMemories.value.filter((m) => m.source === 'inferred' && !m.is_confirmed)
)

const tabs = computed(() => {
  const list = [
    { key: 'user', label: '我的记忆' },
    { key: 'tenant', label: '企业记忆' },
  ]
  if (pendingMemories.value.length) {
    list.push({ key: 'pending', label: `待确认(${pendingMemories.value.length})` })
  } else {
    list.push({ key: 'pending', label: '待确认' })
  }
  return list
})

function categoryLabel(c) {
  return { preference: '偏好', style: '风格', brand: '品牌', industry: '行业' }[c] || c
}

function sourceLabel(m) {
  return m.source === 'inferred' ? 'AI 推断' : '手动'
}

function canDelete(item) {
  if (item.scope === 'user') return true
  return isAdmin.value
}

async function loadMemories() {
  loading.value = true
  try {
    const [userList, tenantList] = await Promise.all([
      agentApi.listMemories({ scope: 'user' }),
      agentApi.listMemories({ scope: 'tenant' }),
    ])
    userMemories.value = userList || []
    tenantMemories.value = tenantList || []
  } catch (e) {
    if (!shouldSilenceLoadError(e)) {
      toastApiError(e, '加载失败')
    }
  } finally {
    loading.value = false
  }
}

async function handleConfirm(item) {
  try {
    await agentApi.confirmMemory(item.id)
    uni.showToast({ title: '已确认', icon: 'success' })
    await loadMemories()
  } catch (e) {
    toastApiError(e, '确认失败')
  }
}

function handleDelete(item) {
  uni.showModal({
    title: '删除记忆',
    content: '删除后 Agent 将不再使用这条记忆，确定删除？',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await agentApi.deleteMemory(item.id)
        uni.showToast({ title: '已删除', icon: 'success' })
        await loadMemories()
      } catch (e) {
        toastApiError(e, '删除失败')
      }
    },
  })
}

onLoad(async () => {
  const user = await ensureSession()
  if (!user?.permissions?.includes('content.create')) {
    uni.showToast({ title: '无权限', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 500)
    return
  }
  isAdmin.value = hasPermission(user.permissions, 'tenant.manage')
})

onShow(loadMemories)
</script>

<template>
  <view class="page">
    <view class="hint">
      Agent 创作时会参考已确认的记忆；与「我的偏好」不同，此处为结构化事实。
    </view>

    <view class="tabs">
      <view
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </view>
    </view>

    <view v-if="loading" class="loading">加载中…</view>

    <template v-else-if="activeTab === 'user'">
      <view v-if="!userMemories.length" class="empty">暂无个人记忆</view>
      <view v-for="item in userMemories" :key="item.id" class="card">
        <text class="card__text">{{ item.fact_text }}</text>
        <view class="card__meta">
          <text class="tag">{{ sourceLabel(item) }}</text>
          <text v-if="!item.is_confirmed" class="tag warn">待确认</text>
          <text class="meta-text">{{ categoryLabel(item.category) }}</text>
        </view>
        <view class="card__actions">
          <text
            v-if="item.source === 'inferred' && !item.is_confirmed"
            class="action primary"
            @click="handleConfirm(item)"
          >
            确认
          </text>
          <text class="action danger" @click="handleDelete(item)">删除</text>
        </view>
      </view>
    </template>

    <template v-else-if="activeTab === 'tenant'">
      <view v-if="!isAdmin" class="hint admin-hint">企业记忆全公司可见；仅管理员可删除。</view>
      <view v-if="!tenantMemories.length" class="empty">暂无企业记忆</view>
      <view v-for="item in tenantMemories" :key="item.id" class="card">
        <text class="card__text">{{ item.fact_text }}</text>
        <view class="card__meta">
          <text class="tag">{{ sourceLabel(item) }}</text>
          <text class="meta-text">{{ categoryLabel(item.category) }}</text>
        </view>
        <view v-if="canDelete(item)" class="card__actions">
          <text class="action danger" @click="handleDelete(item)">删除</text>
        </view>
      </view>
    </template>

    <template v-else>
      <view v-if="!pendingMemories.length" class="empty">暂无待确认的 AI 推断记忆</view>
      <view v-for="item in pendingMemories" :key="item.id" class="card">
        <text class="card__text">{{ item.fact_text }}</text>
        <view class="card__meta">
          <text class="tag warn">AI 推断 · 待确认</text>
        </view>
        <view class="card__actions">
          <text class="action primary" @click="handleConfirm(item)">确认并记住</text>
          <text class="action danger" @click="handleDelete(item)">不要记住</text>
        </view>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 24rpx;
  padding-bottom: 48rpx;
}
.hint {
  font-size: 24rpx;
  color: #666;
  line-height: 1.5;
  margin-bottom: 20rpx;
}
.admin-hint {
  background: #e6f4ff;
  color: #1677ff;
  padding: 16rpx 20rpx;
  border-radius: 8rpx;
  margin-bottom: 16rpx;
}
.tabs {
  display: flex;
  background: #fff;
  border-radius: 12rpx;
  margin-bottom: 20rpx;
  overflow: hidden;
}
.tab {
  flex: 1;
  text-align: center;
  padding: 20rpx 8rpx;
  font-size: 26rpx;
  color: #666;
}
.tab.active {
  color: #1677ff;
  font-weight: 600;
  background: #e6f4ff;
}
.loading,
.empty {
  text-align: center;
  color: #999;
  font-size: 28rpx;
  padding: 80rpx 0;
}
.card {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
}
.card__text {
  display: block;
  font-size: 28rpx;
  line-height: 1.6;
  color: #333;
  margin-bottom: 12rpx;
}
.card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 12rpx;
}
.tag {
  font-size: 22rpx;
  color: #666;
  background: #f5f5f5;
  padding: 4rpx 12rpx;
  border-radius: 6rpx;
}
.tag.warn {
  color: #d48806;
  background: #fff7e6;
}
.meta-text {
  font-size: 22rpx;
  color: #999;
}
.card__actions {
  display: flex;
  gap: 24rpx;
  justify-content: flex-end;
}
.action {
  font-size: 26rpx;
}
.action.primary {
  color: #1677ff;
}
.action.danger {
  color: #ff4d4f;
}
</style>
