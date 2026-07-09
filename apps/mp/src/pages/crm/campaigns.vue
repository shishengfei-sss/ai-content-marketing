<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { crmApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20

const statusLabels = {
  draft: '草稿',
  active: '进行中',
  paused: '暂停',
  completed: '已完成',
  cancelled: '已取消',
}

async function loadData() {
  loading.value = true
  try {
    await ensureSession()
    const data = await crmApi.listCampaigns({ page: page.value, page_size: pageSize })
    items.value = data.items || []
    total.value = data.total ?? 0
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function goDetail(item) {
  uni.navigateTo({ url: `/pages/crm/campaign-detail?id=${item.id}` })
}

onShow(loadData)
</script>

<template>
  <view class="page">
    <view class="hero">
      <text class="hero__sub">{{ loading ? '加载中…' : `共 ${total} 个活动` }}</text>
    </view>

    <view v-if="loading" class="empty">加载中…</view>
    <view v-else-if="!items.length" class="empty">暂无营销活动</view>
    <view v-else class="list">
      <view v-for="item in items" :key="item.id" class="card" @click="goDetail(item)">
        <view class="card__head">
          <text class="card__title">{{ item.name }}</text>
          <text class="status">{{ statusLabels[item.status] || item.status }}</text>
        </view>
        <text class="card__meta">线索 {{ item.lead_count ?? 0 }} · 内容 {{ item.content_count ?? 0 }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 12px;
  box-sizing: border-box;
}

.hero {
  margin-bottom: 12px;
}

.hero__sub {
  color: #64748b;
  font-size: 13px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
}

.card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.card__title {
  font-size: 16px;
  font-weight: 600;
}

.status {
  font-size: 12px;
  color: #1677ff;
  background: #e6f4ff;
  padding: 2px 8px;
  border-radius: 4px;
}

.card__meta {
  display: block;
  margin-top: 6px;
  color: #64748b;
  font-size: 13px;
}

.empty {
  text-align: center;
  color: #94a3b8;
  padding: 40px 0;
}
</style>
