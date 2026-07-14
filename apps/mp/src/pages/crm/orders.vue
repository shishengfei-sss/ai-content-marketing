<script setup>
import { ref } from 'vue'
import { crmApi } from '@/utils/api'
import { ORDER_STATUS_LABEL } from '@/utils/crmConstants'
import CrmEntityListPage from '@/components/crm/CrmEntityListPage.vue'

function goDetail(item) {
  uni.navigateTo({ url: `/pages/crm/order-detail?id=${item.id}` })
}
</script>

<template>
  <view class="page">
    <CrmEntityListPage
      entity-type="order"
      entity-label="订单"
      all-view-label="全部订单"
      empty-text="暂无订单"
      search-placeholder="搜索订单主题、编号"
      title-field="title"
      :format-status="(s) => ORDER_STATUS_LABEL[s] || s"
      :fetch-list="(params) => crmApi.listOrders(params)"
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
