<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { crmApi } from '@/utils/api'
import { DEAL_STATUS_LABEL } from '@/utils/crmConstants'
import CrmEntityListPage from '@/components/crm/CrmEntityListPage.vue'
import DealKanbanH5 from '@/components/crm/DealKanbanH5.vue'

const viewMode = ref(uni.getStorageSync('mp_deals_view_mode') || 'list')
const kanbanRef = ref(null)
const listRef = ref(null)

function setViewMode(mode) {
  viewMode.value = mode
  uni.setStorageSync('mp_deals_view_mode', mode)
}

function goDetail(item) {
  uni.navigateTo({ url: `/pages/crm/deal-detail?id=${item.id}` })
}

function formatStatus(status) {
  return DEAL_STATUS_LABEL[status] || status
}

onShow(() => {
  if (viewMode.value === 'kanban') kanbanRef.value?.reload?.()
  else listRef.value?.reload?.()
})
</script>

<template>
  <view class="page">
    <view class="mode-bar">
      <view class="mode-tabs">
        <view class="mode-tab" :class="{ 'mode-tab--active': viewMode === 'list' }" @tap="setViewMode('list')">列表</view>
        <view class="mode-tab" :class="{ 'mode-tab--active': viewMode === 'kanban' }" @tap="setViewMode('kanban')">看板</view>
      </view>
    </view>

    <CrmEntityListPage
      v-if="viewMode === 'list'"
      ref="listRef"
      entity-type="deal"
      entity-label="商机"
      all-view-label="全部商机"
      empty-text="暂无商机"
      search-placeholder="搜索商机名称、编号"
      title-field="title"
      :format-status="formatStatus"
      :fetch-list="(params) => crmApi.listDeals(params)"
      @card-click="goDetail"
    />

    <DealKanbanH5 v-else ref="kanbanRef" @go-detail="goDetail" />
  </view>
</template>

<style scoped>
.page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
  padding: 12px;
  box-sizing: border-box;
}

.mode-bar {
  flex-shrink: 0;
  margin-bottom: 10px;
}

.mode-tabs {
  display: flex;
  background: #fff;
  border-radius: 10px;
  padding: 4px;
  border: 1px solid #e2e8f0;
}

.mode-tab {
  flex: 1;
  text-align: center;
  padding: 8px 0;
  font-size: 14px;
  color: #64748b;
  border-radius: 8px;
}

.mode-tab--active {
  background: #1677ff;
  color: #fff;
  font-weight: 600;
}
</style>
