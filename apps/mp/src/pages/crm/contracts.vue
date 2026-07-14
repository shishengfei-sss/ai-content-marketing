<script setup>
import { crmApi } from '@/utils/api'
import { CONTRACT_STATUS_LABEL } from '@/utils/crmConstants'
import CrmEntityListPage from '@/components/crm/CrmEntityListPage.vue'
</script>

<template>
  <view class="page">
    <CrmEntityListPage
      entity-type="contract"
      entity-label="合同"
      all-view-label="全部合同"
      empty-text="暂无合同"
      search-placeholder="搜索合同主题、编号"
      title-field="title"
      :format-status="(s) => CONTRACT_STATUS_LABEL[s] || s"
      :fetch-list="(params) => crmApi.listContracts(params)"
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
