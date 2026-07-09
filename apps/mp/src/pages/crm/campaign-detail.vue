<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'

const campaignId = ref('')
const loading = ref(false)
const campaign = ref(null)

const statusLabels = {
  draft: '草稿',
  active: '进行中',
  paused: '暂停',
  completed: '已完成',
  cancelled: '已取消',
}

async function loadDetail() {
  if (!campaignId.value) return
  loading.value = true
  try {
    await ensureSession()
    campaign.value = await crmApi.getCampaign(campaignId.value)
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onLoad((query) => {
  campaignId.value = query.id || ''
  loadDetail()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="empty">加载中…</view>
    <view v-else-if="campaign" class="card">
      <view class="head">
        <text class="title">{{ campaign.name }}</text>
        <text class="status">{{ statusLabels[campaign.status] || campaign.status }}</text>
      </view>
      <view class="stats">
        <view class="stat">
          <text class="stat__value">{{ campaign.lead_count ?? 0 }}</text>
          <text class="stat__label">关联线索</text>
        </view>
        <view class="stat">
          <text class="stat__value">{{ campaign.content_count ?? 0 }}</text>
          <text class="stat__label">关联内容</text>
        </view>
      </view>
      <text v-if="campaign.goal" class="meta">目标：{{ campaign.goal }}</text>
      <text v-if="campaign.description" class="desc">{{ campaign.description }}</text>
    </view>
    <view v-else class="empty">活动不存在</view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 12px;
}

.card {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.status {
  font-size: 12px;
  color: #1677ff;
}

.stats {
  display: flex;
  gap: 16px;
  margin-top: 16px;
}

.stat {
  flex: 1;
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}

.stat__value {
  display: block;
  font-size: 22px;
  font-weight: 600;
  color: #1677ff;
}

.stat__label {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.meta,
.desc {
  display: block;
  margin-top: 12px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}

.empty {
  text-align: center;
  color: #94a3b8;
  padding: 40px 0;
}
</style>
