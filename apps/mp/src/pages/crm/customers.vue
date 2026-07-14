<script setup>
import { crmApi } from '@/utils/api'
import CrmEntityListPage from '@/components/crm/CrmEntityListPage.vue'

function goDetail(item) {
  uni.navigateTo({ url: `/pages/crm/customer-detail?id=${item.id}` })
}

function openCreate() {
  uni.navigateTo({ url: '/pages/crm/customer-create' })
}
</script>

<template>
  <view class="page">
    <CrmEntityListPage
      entity-type="customer"
      entity-label="客户"
      all-view-label="全部客户"
      empty-text="暂无客户"
      search-placeholder="搜索公司、联系人、手机"
      title-field="company_name"
      :fetch-list="(params) => crmApi.listCustomers(params)"
      create-permission="crm.customer.create"
      create-url="/pages/crm/customer-create"
      @card-click="goDetail"
      @create="openCreate"
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
