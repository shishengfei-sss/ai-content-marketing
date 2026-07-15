<script setup>
import { crmApi } from '@/utils/api'
import CrmEntityListPage from '@/components/crm/CrmEntityListPage.vue'

const STATUS_LABEL = {
  draft: '草稿',
  active: '进行中',
  paused: '暂停',
  completed: '已完成',
  cancelled: '已取消',
}

function goDetail(item) {
  uni.navigateTo({ url: `/pages/crm/campaign-detail?id=${item.id}` })
}
</script>

<template>
  <view class="page">
    <CrmEntityListPage
      entity-type="campaign"
      entity-label="营销活动"
      all-view-label="全部活动"
      empty-text="暂无营销活动"
      search-placeholder="搜索活动名称"
      title-field="name"
      :format-status="(s) => STATUS_LABEL[s] || s"
      :fetch-list="(params) => crmApi.listCampaigns(params)"
      @card-click="goDetail"
    />
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
</style>
